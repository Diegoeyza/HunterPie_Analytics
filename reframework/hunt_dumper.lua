--
-- HuntDumper (R1) — REFramework -> HunterPie-fork-compatible hunt dumps
--
-- Writes ONE JSON per successful quest to:
--   reframework/data/HuntExports/<hash>_<yyyyMMdd_HHmmss>.json
-- in the same schema the analytics importer (backend/app/import_hunt.py) already
-- reads, so `./import.sh` and the dashboard Import button work unchanged.
--
-- Scope: real monster id (active em set), max HP, polled HP curve, quest
-- metadata, player identity, quest-end damage TOTALS, the 30 quest awards and
-- the LOCAL player's weapon name. Per-player weapon classes/curves come from
-- HunterPie. Never throws into the game.
--
-- @repo local (Hunterpie_Analytics/reframework)
--

local re = re
local sdk = sdk
local json = json
local log = log
local imgui = imgui
local os = os
local io = io

local VERSION = "0.12.3-diag"
local OUT_SUBDIR = "HuntExports"
local CONFIG_FILE = "hunt_dumper.json"
local GAME_TYPE = 2
local SESSION_QUEST = 2
local HP_POLL_SECONDS = 1.0
local DAMAGE_AWARD_FIELD = "award05" -- award id 4 (= damage); see better_hunter_highlights

-- ---------------------------------------------------------------------------
-- small helpers
-- ---------------------------------------------------------------------------

local function safe(fn, ...)
    local ok, res = pcall(fn, ...)
    if ok then return res end
    return nil
end

local function safe_str(v)
    if v == nil then return nil end
    local t = type(v)
    if t == "string" or t == "number" or t == "boolean" then return v end
    return tostring(v)
end

local function typecall(typeName, methodName, obj)
    local td = safe(sdk.find_type_definition, typeName)
    if not td then return nil end
    local m = safe(function() return td:get_method(methodName .. "()") end)
        or safe(function() return td:get_method(methodName) end)
    if not m then return nil end
    return safe(function() return m:call(obj) end)
end

local function iso(epoch)
    if epoch == nil then return nil end
    local secs = math.floor(epoch)
    local ms = math.floor((epoch - secs) * 1000 + 0.5)
    if ms >= 1000 then secs, ms = secs + 1, ms - 1000 end
    return os.date("!%Y-%m-%dT%H:%M:%S", secs)
        .. string.format(".%03dZ", ms)
end

local QuestUtil = safe(sdk.find_type_definition, "app.QuestUtil")
local utc_method = QuestUtil and safe(function() return QuestUtil:get_method("getUTCTime()") end)
local function utc_now()
    if not utc_method then return os.time() end
    return safe(function() return utc_method:call(nil) end) or os.time()
end

local function collect(list, maxItems)
    local out = {}
    if list == nil then return out end
    local cnt = safe(function() return list.get_Count end)
    local item = safe(function() return list.get_Item end)
    if cnt ~= nil and item ~= nil then
        local n = safe(function() return cnt:call(list) end) or 0
        if maxItems and n > maxItems then n = maxItems end
        for i = 0, n - 1 do
            out[#out + 1] = safe(function() return item:call(list, i) end)
        end
        return out
    end
    for i = 0, 64 do
        if maxItems and i >= maxItems then break end
        local v = safe(function() return list[i] end)
        if v == nil then break end
        out[#out + 1] = v
    end
    return out
end

-- Read an instance field by name via the field's get_data. `obj:get_field()`
-- returns nil for several of the Hunter/Wilds structs, but the field
-- descriptor's get_data(obj) works (same path the probe uses).
local function field_value(obj, fieldName)
    if obj == nil then return nil end
    local td = safe(function() return obj:get_type_definition() end)
    if not td then return nil end
    for _, f in ipairs(safe(function() return td:get_fields() end) or {}) do
        if safe(function() return f:get_name() end) == fieldName then
            local is_static = safe(function() return f:is_static() end)
            return safe(function() return f:get_data(is_static and nil or obj) end)
        end
    end
    return nil
end

-- Boxed System.Single (System.Single[] elements) -> number.
local function boxed_float(elem)
    if elem == nil then return nil end
    local v = field_value(elem, "m_value")
    if type(v) == "number" then return v end
    if type(elem) == "number" then return elem end
    return nil
end

-- output directory, derived from this script's own path (autorun/ -> data/)
local function resolve_out_dir()
    local info = debug.getinfo(1, "S")
    local src = (info and info.source or ""):gsub("^@", "")
    if src == "" then return nil end
    -- strip filename -> .../reframework/autorun ; then strip autorun
    local dir = src:match("^(.*)[/\\][^/\\]+$")
    if not dir then return nil end
    local ref = dir:match("^(.*)[/\\][^/\\]+$")
    if not ref then return nil end
    local sep = "\\"
    if src:find("/") then sep = "/" end
    return ref .. sep .. "data" .. sep .. OUT_SUBDIR
end

local OUT_DIR = resolve_out_dir()

local function ensure_dir()
    if OUT_DIR then
        safe(os.execute, 'mkdir "' .. OUT_DIR .. '" 2>nul')
    end
end

-- ---------------------------------------------------------------------------
-- config
-- ---------------------------------------------------------------------------

local config = { enabled = true, debug = false, last_status = "idle" }

local function load_config()
    local loaded = json.load_file(CONFIG_FILE)
    if loaded then
        if type(loaded.enabled) == "boolean" then config.enabled = loaded.enabled end
        if type(loaded.debug) == "boolean" then config.debug = loaded.debug end
    else
        json.dump_file(CONFIG_FILE, { enabled = true, debug = false })
    end
end
local function save_config() json.dump_file(CONFIG_FILE, { enabled = config.enabled, debug = config.debug }) end
local function dlog(fmt, ...) if config.debug then log.info(string.format("[HuntDumper] " .. fmt, ...)) end end

-- ---------------------------------------------------------------------------
-- quest state
-- ---------------------------------------------------------------------------

local state = nil
local awards = {} -- userIndex+1 -> { index, awards={id->count}, channels } (multiplayer)
local weapon_name, self_weapon_id -- self weapon name lookup (defined below)

-- Forward declaration: the party-HP poll below calls it.
local read_instanced_hp

-- ---------------------------------------------------------------------------
-- party HP (Survival tab)
-- ---------------------------------------------------------------------------

local PHP_CHANGE = 0.005   -- emit a sample on >=0.5% HP change
local PHP_HEARTBEAT = 5.0  -- ...or at least every 5 s

-- Call a method on the object's OWN type definition. The old code guessed
-- class names (app.cHunterHealth, app.cHealthManager) and silently lost the
-- whole chain when a guess was wrong; this works for any runtime type.
local function call_method(obj, name)
    if obj == nil then return nil end
    local td = safe(function() return obj:get_type_definition() end)
    if not td then return nil end
    local m = safe(function() return td:get_method(name .. "()") end)
        or safe(function() return td:get_method(name) end)
    if not m then return nil end
    local v = safe(function() return m:call(obj) end)
    if type(v) == "number" then return v end
    local b = boxed_float(v)
    if b ~= nil then return b end
    return v
end

local function type_name(obj)
    return safe_str(safe(function()
        return obj:get_type_definition():get_full_name()
    end))
end

-- Health of a character object -> { hp, max_hp, red, fail, char_type }
-- (hp/red are 0..1 fractions). Shared by the party list and the master player.
local function health_of(ch)
    local info = { char_type = type_name(ch) }

    -- get_Character may be the HunterCharacter itself or a wrapper whose
    -- real character lives in <Character>k__BackingField (master-player path).
    local hc = ch
    local hh = call_method(hc, "get_HunterHealth")
    if hh == nil then
        local wrapped = field_value(ch, "<Character>k__BackingField")
            or field_value(ch, "_Character")
        if wrapped then
            hc = wrapped
            info.char_type = type_name(hc)
            hh = call_method(hc, "get_HunterHealth")
        end
    end
    if hh == nil then
        local st = call_method(hc, "get_HunterStatus")
            or field_value(hc, "<HunterStatus>k__BackingField")
        hh = st and (field_value(st, "_HunterHealth")
                     or field_value(st, "<HunterHealth>k__BackingField")
                     or field_value(st, "_Health"))
    end
    if hh == nil then
        info.fail = "no_hunter_health"
        return info
    end

    local mgr = call_method(hh, "get_HealthMgr")
        or field_value(hh, "<HealthMgr>k__BackingField")
        or field_value(hh, "_HealthMgr")
        or field_value(hh, "_HealthManager")
    if mgr == nil then
        info.fail = "no_health_mgr"
        return info
    end
    local hp = call_method(mgr, "get_Health")
    local mx = call_method(mgr, "get_MaxHealth")
    if mx == nil then mx = call_method(mgr, "get_MaxHealthValue") end
    if hp == nil then hp = call_method(hh, "get_Health") end
    if mx == nil then mx = call_method(hh, "get_MaxHealth") end
    if type(hp) ~= "number" or type(mx) ~= "number" or mx <= 0 then
        info.fail = "no_hp_value"
        return info
    end
    info.hp = hp / mx
    info.max_hp = mx
    local red = call_method(hh, "get_RedHealth")
    if type(red) == "number" and red >= 0 then
        -- red is reported on the same scale as HP; normalise just in case.
        info.red = red <= mx and (red / mx) or nil
    end
    return info
end

-- The character object behind one instanced player. Different game builds
-- name the accessor differently; try the known ones plus the backing field.
local function character_of(inst, pi)
    for _, name in ipairs({ "get_Character", "get_Hunter", "get_Player",
                            "get_CharacterInfo", "get_Pl" }) do
        local v = pi and call_method(pi, name)
        if v ~= nil and v ~= 0 then return v end
    end
    for _, name in ipairs({ "get_Hunter", "get_Character" }) do
        local v = call_method(inst, name)
        if v ~= nil and v ~= 0 then return v end
    end
    return field_value(inst, "<Character>k__BackingField")
        or field_value(inst, "_Character")
end

-- One instanced party member -> { hp, max_hp, red, pi, char_type, fail }.
-- Declared early, so this is the actual body.
read_instanced_hp = function(inst)
    local info = {}
    local pi = call_method(inst, "get_PlayerInfo")
    info.pi = pi
    local ch = character_of(inst, pi)
    if ch == nil or ch == 0 then
        info.fail = "no_character"
        return info
    end
    local h = health_of(ch)
    info.char_type = h.char_type
    if type(h.hp) ~= "number" then
        info.fail = h.fail
        return info
    end
    info.hp, info.max_hp, info.red = h.hp, h.max_hp, h.red
    return info
end

-- Locate the instanced party list. Field names drift between game builds, so
-- fall back to scanning PlayerManager's fields for an "Instanced"/"PlayerList"
-- field rather than trusting one hardcoded name.
local function instanced_list(pm)
    local list = field_value(pm, "_InstancedPlayerList")
        or field_value(pm, "<InstancedPlayerList>k__BackingField")
        or field_value(pm, "_PlayerList")
    if list then return list end
    local td = safe(function() return pm:get_type_definition() end)
    for _, f in ipairs(safe(function() return td and td:get_fields() end) or {}) do
        local n = safe(function() return f:get_name() end)
        if n and (n:find("Instanced") or n:find("PlayerList")) then
            local v = safe(function() return f:get_data(pm) end)
            if v then return v end
        end
    end
    return nil
end

local function instanced_array(pm)
    local list = instanced_list(pm)
    if not list then return nil end
    return field_value(list, "_Array")
        or field_value(list, "<Array>k__BackingField")
        or field_value(list, "_Items")
        or list
end

local function array_get(arr, i)
    local v = safe(function() return arr[i] end)
    if v == nil then
        -- Some lists expose get_Item(int) instead of a raw array.
        local td = safe(function() return arr:get_type_definition() end)
        local m = td and safe(function() return td:get_method("get_Item(System.Int32)") end)
        if m then
            v = safe(function() return m:call(arr, i) end)
            if v == nil then v = safe(function() return m:call(arr, i + 1) end) end
        end
    end
    return v
end

-- Diag: snapshot the three identity orders (compact ptrs, slot ptrs,
-- users names) so a mid-quest reorder is visible post-hoc. Throttled to
-- ~30s plus always on change; bounded. Passive: no sampling impact.
local function diag_snapshot_orders(pm, now, force)
    if not state or not state.diag_orders then return end
    if not force and now - (state.diag_order_last or 0) < 30 then return end
    state.diag_order_last = now
    local arr = safe(function() return instanced_array(pm) end)
    local plist = safe(function() return field_value(pm, "_PlayerList") end)
    local compact, slots, users = {}, {}, {}
    if arr then
        for i = 0, 7 do
            local inst = safe(function() return array_get(arr, i) end)
            if inst then compact[#compact + 1] = tostring(inst) end
        end
    end
    if plist then
        for i = 0, 7 do
            local inst = safe(function() return array_get(plist, i) end)
            if inst then slots[#slots + 1] = tostring(inst) end
        end
    end
    for i = 0, 7 do
        local u = state.users and state.users[i]
        users[#users + 1] = (u and u.name) or "?"
    end
    local key = table.concat(compact, ",") .. "|" .. table.concat(slots, ",")
    if not force and key == state.diag_order_key then return end
    if state.diag_order_key ~= nil and key ~= state.diag_order_key then
        state.diag_order_changes = (state.diag_order_changes or 0) + 1
    end
    state.diag_order_key = key
    if #state.diag_orders < 60 then
        state.diag_orders[#state.diag_orders + 1] =
            { t = now, compact = compact, slots = slots, users = users }
    end
end

-- Diag: method names containing identity-ish words, one discovery dump per
-- type. Reveals untried accessors (e.g. a working per-object user index).
local _diag_type_cache = {}
local function diag_type_methods(obj)
    local td = safe(function() return obj:get_type_definition() end)
    local tn = safe(function() return td and td:get_full_name() end) or "?"
    if _diag_type_cache[tn] then return _diag_type_cache[tn] end
    local out = {}
    for _, m in ipairs(safe(function() return td and td:get_methods() end) or {}) do
        local n = safe(function() return m:get_name() end)
        if n and (n:find("Name") or n:find("User") or n:find("Index")
                  or n:find("Slot") or n:find("Member") or n:find("Owner")) then
            out[#out + 1] = n
        end
    end
    _diag_type_cache[tn] = { type = tn, methods = out }
    return _diag_type_cache[tn]
end

-- Diag: try name-ish accessors on control / player-info / character.
-- Records only non-empty hits; empty means the accessor is dead here.
local _DIAG_NAME_METHODS = { "get_PlayerName", "get_Name", "get_PlName",
    "get_UserName", "get_HunterName", "get_CharacterName", "get_OwnerName" }
local function diag_probe_names(inst, pi, ch)
    local out = {}
    local function trym(obj, tag)
        if obj == nil then return end
        for _, m in ipairs(_DIAG_NAME_METHODS) do
            local v = safe(function() return call_method(obj, m) end)
            if type(v) == "string" and v ~= "" then
                out[tag .. "." .. m] = v
            end
        end
    end
    trym(inst, "inst")
    trym(pi, "pi")
    trym(ch, "ch")
    return out
end

-- Samples are keyed by USER SLOT, never by name. The same instance can
-- resolve to different names across polls (context vs roster), and a bad
-- name used to merge the host's HP into the local player's series. The slot
-- is stable; the display name is only resolved once, at dump time.
-- The observed name is still remembered on the series (rec.name) so the
-- dump-time assignment can cross-check it: slot first, name second, list
-- position last. Position must never win over slot (SOS slots can be 6
-- while the list position is 1), or two hunters' HP series swap.
local function record_hp(key, name, h, now)
    if key == nil or type(h.hp) ~= "number" then return false end
    state.php = state.php or {}
    local rec = state.php[key]
    if rec == nil then
        rec = { samples = {}, last = nil, last_emit = 0 }
        state.php[key] = rec
    end
    if type(name) == "string" and name ~= "" then rec.name = name end
    local changed = rec.last == nil or math.abs(h.hp - rec.last) >= PHP_CHANGE
    local heartbeat = (now - (rec.last_emit or 0)) >= PHP_HEARTBEAT
    if changed or heartbeat then
        rec.samples[#rec.samples + 1] = {
            t = now, hp = h.hp, red = h.red, max_hp = h.max_hp,
        }
        rec.last = h.hp
        rec.last_emit = now
    end
    return true
end

-- Slot-indexed name map. `_InstancedPlayerList` is compact (join order), so
-- using its index as a roster slot can swap player names. `_PlayerList` is a
-- plain cPlayerManageControl[] indexed by user slot, so match the SAME object
-- by identity and read the slot from there.
local function player_list_slots(pm)
    local out = {}
    local plist = field_value(pm, "_PlayerList")
    if plist == nil then return out end
    for i = 0, 7 do
        local inst = safe(function() return array_get(plist, i) end)
        if inst then out[tostring(inst)] = i end
    end
    return out
end

-- Player names: the context chain (get_ContextHolder():get_Pl()) is nil on
-- some builds, so fall back to the quest roster. _QuestPlayerList holds the
-- user index of each instanced slot, which maps back to NetworkManager users.
local function quest_player_indices(pm)
    local q = field_value(pm, "_QuestPlayerList")
    local out = {}
    if q == nil then return out end
    for i = 0, 7 do
        local v = safe(function() return array_get(q, i) end)
        v = boxed_float(v) or safe(function() return sdk.to_int64(v) end)
        -- True user indices are small whole numbers (0-7). This build reads
        -- garbage here instead (observed 1067109872, 1620998912 — misread
        -- floats/pointers), and an unfiltered value poisons the sample key,
        -- orphaning the whole HP series at dump time. Reject anything else.
        if type(v) == "number" and v >= 0 and v < 8
            and math.floor(v) == v then out[i] = v end
    end
    return out
end

local function roster_name(i, qi)
    local users = state.users or {}
    if type(qi) == "number" then
        for _, u in pairs(users) do
            if u and u.idx == qi and u.name then return u.name, "roster_qi" end
        end
        local u = users[qi]
        if u and u.name then return u.name, "roster_pos" end
    end
    local u = users[i]
    if u and u.name then return u.name, "roster_i" end
    return nil, nil
end

-- A player-object user index, when the build exposes one. That is the most
-- direct link to NetworkManager's user list, so try it before any positional
-- heuristic.
local function player_index(inst, pi)
    for _, m in ipairs({ "get_UserIndex", "get_PlayerIndex", "get_PlayerNo" }) do
        local v = boxed_float(safe(function() return call_method(inst, m) end))
        if type(v) == "number" and v >= 0 and v < 8 then return v end
    end
    for _, fn in ipairs({ "_UserIndex", "_PlayerIndex", "_PlayerNo" }) do
        local v = boxed_float(field_value(inst, fn))
        if type(v) == "number" and v >= 0 and v < 8 then return v end
    end
    if pi then
        for _, m in ipairs({ "get_UserIndex", "get_PlayerIndex",
                             "get_PlayerNo" }) do
            local v = boxed_float(safe(function() return call_method(pi, m) end))
            if type(v) == "number" and v >= 0 and v < 8 then return v end
        end
        for _, fn in ipairs({ "_UserIndex", "_PlayerIndex", "_PlayerNo" }) do
            local v = boxed_float(field_value(pi, fn))
            if type(v) == "number" and v >= 0 and v < 8 then return v end
        end
    end
    return nil
end

local function users_by_index(idx)
    for _, u in pairs(state.users or {}) do
        if u and (u.idx == idx or u.slot == idx) and u.name then
            return u.name
        end
    end
    return nil
end

local function name_of(inst, pi, i, qi, slot)
    local ctx = call_method(inst, "get_ContextHolder")
    local pl = ctx and (call_method(ctx, "get_Pl")
        or call_method(ctx, "get_Player")
        or field_value(ctx, "_Pl"))
    local n = safe_str(pl and (call_method(pl, "get_PlayerName")
        or call_method(pl, "get_Name")))
    if n then return n, "context" end
    n = safe_str(pi and (call_method(pi, "get_PlayerName")
        or call_method(pi, "get_PlName")))
    if n then return n, "playerinfo" end
    n = safe_str(call_method(inst, "get_PlayerName"))
    if n then return n, "inst" end
    local idx = player_index(inst, pi)
    if idx then
        n = users_by_index(idx)
        if n then return n, "user_index" end
    end
    if type(qi) == "number" then
        -- The quest roster maps this instance to its true user index.
        -- Identity, not position: lobby order and join order often differ
        -- (SOS), so this must beat every positional guess below. A
        -- users[slot] hit further down proves nothing when the two orders
        -- disagree — it silently relabels one hunter as another.
        n = users_by_index(qi)
        if n then return n, "roster_qi" end
    end
    if type(slot) == "number" then
        -- The compact user list has no entry at this control slot, but the
        -- entry itself records it (SOS slots can be 6 while position is 1).
        for _, u in pairs(state.users or {}) do
            if u and u.slot == slot and u.name then
                return u.name, "user_slot"
            end
        end
        local u = state.users and state.users[slot]
        if u and u.name and (u.slot == nil or u.slot == slot) then
            return u.name, "player_list"
        end
    end
    return roster_name(i, qi)
end

local function poll_party_hp(now)
    state.php_seen = 0
    state.php_fail = 0
    state.php_error = nil
    local PM = safe(sdk.find_type_definition, "app.PlayerManager")
    local pm = PM and safe(function() return sdk.get_managed_singleton("app.PlayerManager") end)
    if not pm then return end

    -- 1) Instanced party list (every hunter in the quest).
    local arr = instanced_array(pm)
    local qidx = quest_player_indices(pm)
    local slots = player_list_slots(pm)
    if arr then
        for i = 0, 7 do
            local inst = array_get(arr, i)
            if inst then
                state.php_seen = state.php_seen + 1
                local r = safe(read_instanced_hp, inst) or {}
                local pi = r.pi
                local slot = slots[tostring(inst)]
                local idx = player_index(inst, pi)
                local n, src = name_of(inst, pi, i, qidx[i], slot)
                if n then r.name = n; r.name_src = src end
                -- Strongest identity first: the player object's user index,
                -- then the quest roster's user index for this instance, then
                -- the _PlayerList position. The list position is join order,
                -- NOT the control slot (SOS lobbies), so it ranks last: it
                -- can only label a series, never identify it.
                local key = idx or qidx[i] or slot or i
                state.php_names = state.php_names or {}
                local u = state.users and state.users[i]
                state.php_names[i] = { name = n, src = src,
                                       slot = slot, idx = idx,
                                       qi = qidx[i], key = key,
                                       roster_self = u and u.is_self or nil,
                                       hp_ok = r.hp_ok, fail = r.fail }
                if not record_hp(key, n, r, now) then
                    state.php_fail = (state.php_fail or 0) + 1
                    state.php_last_fail = r.fail or "unknown"
                end
            end
        end
    end

    -- 2) Master player fallback, ONLY when the party list yielded nobody.
    -- getMasterPlayer() is the quest HOST, not the local hunter: in a hunt
    -- hosted by someone else it must never be recorded under the local
    -- player's name (it used to interleave two hunters' HP in one series).
    if state.php_seen > 0 then return end
    local mp = call_method(pm, "getMasterPlayer")
    if mp then
        local ch = field_value(mp, "<Character>k__BackingField")
            or field_value(mp, "_Character") or mp
        local h = health_of(ch)
        state.master_fail = h.fail
        state.master_hp_ok = type(h.hp) == "number"
        -- getMasterPlayer() is the HOST (slot 0), not the local player. Only
        -- fall back to self_name when the roster proves this is solo.
        local host_name = users_by_index(0)
        if not host_name and state.self_name then
            local n = 0
            for _ in pairs(state.users or {}) do n = n + 1 end
            if n <= 1 then host_name = state.self_name end
        end
        if state.master_hp_ok and host_name then
            record_hp(0, host_name, h, now)
        end
    else
        state.master_fail = "no_master_player"
    end
end

-- Diagnostics for the party-HP chain, embedded in the dump itself (the dump
-- is the one file we know reaches the importer). Lists each instanced player,
-- which accessor produced a character, and the broken link when HP is missing.
local function party_debug()
    local out = { array_found = false, players = {} }
    local PM = safe(sdk.find_type_definition, "app.PlayerManager")
    local pm = PM and safe(function() return sdk.get_managed_singleton("app.PlayerManager") end)
    if not pm then out.fail = "no_player_manager" return out end
    if config.debug then
        out.pm_type = type_name(pm)
        local pmtd = safe(function() return pm:get_type_definition() end)
        out.pm_fields = {}
        for _, f in ipairs(safe(function() return pmtd and pmtd:get_fields() end) or {}) do
            local n = safe(function() return f:get_name() end)
            if n and (n:find("Instanc") or n:find("Player") or n:find("List")) then
                local ft = safe(function()
                    local t = f:get_type()
                    return t and t:get_full_name()
                end)
                out.pm_fields[#out.pm_fields + 1] = { name = n,
                                                     type = safe_str(ft) }
            end
        end
    end
    local list = instanced_list(pm)
    out.list_type = type_name(list)
    local arr = instanced_array(pm)
    if not arr then out.fail = "no_instanced_list" return out end
    out.array_found = true
    out.php_seen = state.php_seen
    out.php_fail = state.php_fail
    out.php_names = state.php_names
    -- Always recorded (not debug-only): the roster order is the only way to
    -- audit series-to-hunter mapping after the fact. Small: two short maps.
    out.qidx = {}
    for k, v in pairs(quest_player_indices(pm)) do out.qidx[k] = v end
    out.users = {}
    for k, u in pairs(state.users or {}) do
        out.users[tostring(k)] = { name = u.name, idx = u.idx,
                                   slot = u.slot, is_self = u.is_self }
    end
    -- Diag (always recorded): order snapshots show compact-vs-slot
    -- reorder events; hook samples show what the award sync carries.
    out.diag_order_changes = state and state.diag_order_changes or 0
    out.diag_orders = state and state.diag_orders or {}
    out.diag_hook = state and state.diag_hook or {}
    out.diag_sync_fields = state and state.diag_sync_fields or nil
    if config.debug then
        out.arr_type = type_name(arr)
        out.player_list = {}
        local plist = field_value(pm, "_PlayerList")
        if plist then
            for i = 0, 7 do
                local inst = array_get(plist, i)
                if inst then
                    local ch = character_of(inst,
                        call_method(inst, "get_PlayerInfo")) or inst
                    local h = safe(function() return health_of(ch) end) or {}
                    local u = state.users and state.users[i]
                    out.player_list[#out.player_list + 1] = {
                        slot = i, ptr = tostring(inst),
                        char_ptr = tostring(ch),
                        name = u and u.name or nil,
                        is_self = u and u.is_self or nil,
                        hp_ok = type(h.hp) == "number", hp = h.hp }
                end
            end
        end
        out.instanced = {}
        for i = 0, 7 do
            local inst = array_get(arr, i)
            if inst then
                local ch = character_of(inst,
                    call_method(inst, "get_PlayerInfo")) or inst
                out.instanced[#out.instanced + 1] = { index = i,
                                                      ptr = tostring(inst),
                                                      char_ptr = tostring(ch) }
            end
        end
    end
    for i = 0, 7 do
        local inst = array_get(arr, i)
        if inst then
            local info = { index = i, inst_type = type_name(inst) }
            local ctx = call_method(inst, "get_ContextHolder")
            local pl = ctx and call_method(ctx, "get_Pl")
            info.name = safe_str(pl and call_method(pl, "get_PlayerName"))
            local n, src = name_of(inst, call_method(inst, "get_PlayerInfo"), i, nil)
            info.resolved_name = n
            info.name_src = src
            local pi = call_method(inst, "get_PlayerInfo")
            info.pi_type = type_name(pi)
            info.diag_names = diag_probe_names(inst, pi, nil)
            if out.diag_types == nil then
                out.diag_types = {
                    inst = diag_type_methods(inst),
                    pi = diag_type_methods(pi),
                }
            end
            do
                local dbg_ch = safe(function()
                    return character_of(inst, pi) end)
                if dbg_ch then
                    local hit = diag_probe_names(nil, nil, dbg_ch)
                    if next(hit) ~= nil then info.diag_names_ch = hit end
                    if out.diag_types.ch == nil then
                        out.diag_types.ch = diag_type_methods(dbg_ch)
                    end
                end
            end
            if config.debug then
                info.user_control = safe(function()
                    return inst:get_IsUserControl() end)
                info.indices = {}
                for _, m in ipairs({ "get_UserIndex", "get_PlayerIndex",
                                     "get_Index", "get_PlayerNo" }) do
                    local v = safe(function() return call_method(inst, m) end)
                    if v ~= nil then info.indices[m] = v end
                end
                for _, fn in ipairs({ "_UserIndex", "_PlayerIndex", "_Index",
                                      "_PlayerNo", "_Slot" }) do
                    local v = field_value(inst, fn)
                    if v ~= nil then info.indices[fn] = v end
                end
                for _, m in ipairs({ "get_UserIndex", "get_PlayerIndex",
                                     "get_Index", "get_PlayerNo" }) do
                    local v = safe(function() return call_method(pi, m) end)
                    if v ~= nil then info.indices["pi." .. m] = v end
                end
                for _, fn in ipairs({ "_UserIndex", "_PlayerIndex", "_Index",
                                      "_PlayerNo", "_Slot" }) do
                    local v = field_value(pi, fn)
                    if v ~= nil then info.indices["pi." .. fn] = v end
                end
            end
            local ch = character_of(inst, pi)
            info.char_type = type_name(ch)
            if ch == nil or ch == 0 then
                -- Record what the player-info object CAN do, so the right
                -- accessor is obvious from one real dump.
                info.pi_methods = {}
                local td = safe(function() return pi and pi:get_type_definition() end)
                for _, m in ipairs(safe(function() return td and td:get_methods() end) or {}) do
                    local n = safe(function() return m:get_name() end)
                    if n then info.pi_methods[#info.pi_methods + 1] = n end
                end
                info.fail = "no_character"
            else
                local h = health_of(ch)
                info.hp_ok = type(h.hp) == "number"
                info.fail = h.fail
                info.hh_type = h.char_type
                if type(h.hp) == "number" then
                    info.hp = h.hp
                    info.max_hp = h.max_hp
                end
            end
            out.players[#out.players + 1] = info
        end
    end
    local mp = call_method(pm, "getMasterPlayer")
    if mp then
        local ch = field_value(mp, "<Character>k__BackingField")
            or field_value(mp, "_Character") or mp
        local h = health_of(ch)
        out.master = { hp_ok = type(h.hp) == "number", fail = h.fail,
                       char_type = h.char_type, ptr = tostring(ch),
                       hp = h.hp, max_hp = h.max_hp }
    else
        out.master = { fail = "no_master_player" }
    end
    return out
end

-- Export shape for one player: { percentage, red_percentage, max_hp, time }.
local function php_health_steps(key)
    if not state or not state.php then return nil end
    local rec = state.php[key]
    if rec == nil or #rec.samples == 0 then return nil end
    local out = {}
    for _, s in ipairs(rec.samples) do
        out[#out + 1] = { percentage = s.hp, red_percentage = s.red,
                          max_hp = s.max_hp, time = iso(s.t) }
    end
    return out
end

-- find the cQuestAwardSync object inside a hook's args and its userIndex
local function find_award_sync(args)
    if args == nil then return nil, nil end
    for i = 3, 5 do
        local a = args[i]
        if a ~= nil then
            local mo = safe(function() return sdk.to_managed_object(a) end)
            if mo then
                local v = safe(function() return mo["award05"] end)
                if v ~= nil then return mo, i end
            end
        end
    end
    return nil, nil
end

local function get_active_em_ids()
    local MM = safe(sdk.find_type_definition, "app.MissionManager")
    local mgr = MM and safe(function() return sdk.get_managed_singleton("app.MissionManager") end)
    local dir = mgr and typecall("app.MissionManager", "get_QuestDirector", mgr)
    if not dir then return {} end
    local ids = typecall("app.cQuestDirector", "getActiveEmSet_EmIDs", dir)
    local out = {}
    for _, v in ipairs(collect(ids, 8)) do
        local n = safe(function() return v end)
        if type(n) == "number" then out[#out + 1] = n end
    end
    return out
end

local function get_bosses()
    local QU = safe(sdk.find_type_definition, "app.QuestUtil")
    local getList = QU and safe(function() return QU:get_method("getActiveQuestTargetBossList()") end)
    local keys = getList and safe(function() return getList:call(nil) end)
    if keys == nil then return {} end
    local Taku = safe(sdk.find_type_definition, "app.TargetAccessKeyUtil")
    local getEnemy = Taku and safe(function()
        return Taku:get_method("getEnemyCharacter(app.TARGET_ACCESS_KEY, System.Boolean)")
    end)
    local out = {}
    for _, key in ipairs(collect(keys, 8)) do
        local enemy = getEnemy and safe(function() return getEnemy:call(nil, key, true) end)
        if enemy then out[#out + 1] = enemy end
    end
    return out
end

local function quest_meta()
    local MM = safe(sdk.find_type_definition, "app.MissionManager")
    local mgr = MM and safe(function() return sdk.get_managed_singleton("app.MissionManager") end)
    local dir = mgr and typecall("app.MissionManager", "get_QuestDirector", mgr)
    local aqd = mgr and typecall("app.MissionManager", "get_ActiveQuestData", mgr)
    local m = {}
    if dir then
        m.level = typecall("app.cQuestDirector", "getActiveQuestLv", dir)
        m.time_limit = typecall("app.cQuestDirector", "getActiveTimeLimit", dir)
    end
    if aqd then
        m.max_deaths = typecall("app.cActiveQuestData", "getQuestLife", aqd)
        m.capture = typecall("app.cActiveQuestData", "isClearConditionCapture", aqd)
        m.arena = typecall("app.cActiveQuestData", "isArenaQuest", aqd)
    end
    local param = dir and typecall("app.cQuestDirector", "get_Param", dir)
    if param then
        m.start_weapon_type = typecall("app.cQuestFlowParam", "get_QuestStartWeaponType", param)
    end
    return m
end

local function quest_users()
    local NM = safe(sdk.find_type_definition, "app.NetworkManager")
    local nm = NM and safe(function() return sdk.get_managed_singleton("app.NetworkManager") end)
    if not nm then return {} end
    local uim = safe(function() return nm:call("get_UserInfoManager") end)
        or safe(function() return nm:get_field("<UserInfoManager>k__BackingField") end)
    if not uim then return {} end
    local uil = safe(function() return uim:getUserInfoList(SESSION_QUEST) end)
    local arr = uil and safe(function() return uil._ListInfo end)
    local out = {}
    for i, u in ipairs(collect(arr, 8)) do
        if u then
            local uid = boxed_float(safe(function() return u:get_UserIndex() end))
            out[i - 1] = {
                name = safe_str(safe(function() return u:get_PlName() end)),
                is_self = safe(function() return u:get_IsSelf() end),
                idx = uid,
                -- _PlayerList is indexed by this user/control slot; the list
                -- itself is compact join order, so a slot can be 6 while its
                -- list position is 1 (SOS quests).
                slot = uid,
            }
        end
    end
    return out
end

local function gen_hash()
    local parts = {}
    for _ = 1, 8 do
        parts[#parts + 1] = string.format("%08x", math.random(0, 0x7fffffff))
    end
    return table.concat(parts)
end

-- ---------------------------------------------------------------------------
-- lifecycle
-- ---------------------------------------------------------------------------

local function begin_session()
    if not config.enabled then return end
    math.randomseed(os.time())
    local meta = quest_meta()
    -- Record the local weapon id at quest start (compared to the reward-screen
    -- reading, which the older build used and which looked stable).
    local self_wtype = meta.start_weapon_type
    local self_wid_start = self_weapon_id()
    state = {
        started = utc_now(),
        hash = gen_hash(),
        em_ids = get_active_em_ids(),
        meta = meta,
        users = quest_users(),
        self_name = nil,
        hp = {},          -- [bossIndex] = { {t, norm}, ... }
        max_hp = nil,
        last_poll = 0,
        finished = false,
        self_wtype = self_wtype,
        self_wid_start = self_wid_start,
        php = {},            -- [playerName] = { samples, last, last_emit }
        diag_orders = {},    -- throttled {t, compact=ptr list, slots=ptr list, users=name list}
        diag_order_last = 0,
        diag_order_key = nil,
        diag_order_changes = 0,
        diag_hook = {},      -- bounded on_award_sync arg samples
        diag_sync_fields = nil,
    }
    for _, u in pairs(state.users or {}) do
        if u and u.is_self and u.name then state.self_name = u.name end
    end
    awards = {}
    dlog("quest start: em_ids=%s lv=%s self_type=%s self_id=%s",
        tostring(#state.em_ids), tostring(state.meta.level),
        tostring(self_wtype), tostring(self_wid_start))
end

local function poll()
    if not config.enabled or state == nil or state.finished then return end
    local now = utc_now()
    if now - (state.last_poll or 0) < HP_POLL_SECONDS then return end
    state.last_poll = now
    local bosses = get_bosses()
    for i, enemy in ipairs(bosses) do
        local hm = typecall("app.EnemyCharacter", "get_HealthMgr", enemy)
        if hm then
            local mx = typecall("app.cHealthManager", "get_MaxHealth", hm)
            local norm = typecall("app.cHealthManager", "get_HealthNormalized", hm)
            if mx and mx > 0 then state.max_hp = mx end
            if type(norm) == "number" then
                state.hp[i] = state.hp[i] or {}
                state.hp[i][#state.hp[i] + 1] = { t = now, norm = norm }
            end
        end
    end
    safe(poll_party_hp, now)
    do
        local PM = safe(sdk.find_type_definition, "app.PlayerManager")
        local pm = PM and safe(function() return sdk.get_managed_singleton("app.PlayerManager") end)
        if pm then diag_snapshot_orders(pm, now, false) end
    end
end

-- ace.UnionValue stores raw bytes; award id 4 (damage) is a packed float32.
local UnionType = safe(sdk.find_type_definition, "ace.UnionValue")
local UnionFields = {}
if UnionType then
    for _, f in ipairs(safe(function() return UnionType:get_fields() end) or {}) do
        local n = safe(function() return f:get_name() end)
        if n then UnionFields[n] = f end
    end
end

local function bits_to_float(bits)
    local sign = 1
    if bits >= 2147483648 then sign = -1; bits = bits - 2147483648 end
    local exp = math.floor(bits / 8388608)
    local mant = bits % 8388608
    if exp == 0 then return sign * (mant / 8388608) * 2 ^ -126 end
    if exp == 255 then return 0 end
    return sign * (1 + mant / 8388608) * 2 ^ (exp - 127)
end

local function union_float(v)
    if v == nil then return nil end
    local function b(n)
        local f = UnionFields[n]
        if not f then return 0 end
        return safe(function() return f:get_data(v) end) or 0
    end
    local bits = b("Byte0") + b("Byte1") * 256 + b("Byte2") * 65536 + b("Byte3") * 16777216
    if bits == 0 then return 0 end
    return bits_to_float(bits)
end

-- award id 4 = damage (field award05). All 30 award ids (0..29) live on the
-- cQuestAwardSync packet as award01..award30; award01 is a uint32[4] channel
-- array (better_hunter_highlights). Solo never calls setSharedQuestAwardInfo,
-- so the self player's awards come from get_QuestAwardInfo() instead.
local AWARD_MAX_ID = 29
local DAMAGE_AWARD_ID = 4

-- Read every award field off a cQuestAwardSync object -> { awards={id->v}, channels={4} }
local function read_award_sync(sync)
    local rec = { awards = {} }
    local a1 = safe(function() return sync["award01"] end)
    if a1 ~= nil then
        local ch = {}
        for k = 0, 3 do
            ch[#ch + 1] = safe(function() return a1:get_Item(k) end) or 0
        end
        rec.channels = ch
        rec.awards[0] = (ch[1] or 0) + (ch[2] or 0) + (ch[3] or 0) + (ch[4] or 0)
    end
    for aid = 1, AWARD_MAX_ID do
        local v = safe(function() return sync[string.format("award%02d", aid + 1)] end)
        if type(v) == "number" then rec.awards[aid] = v end
    end
    return rec
end

-- Self player's awards (solo path). get_QuestAwardInfo() is a flat array of
-- ace.UnionValue indexed by award id (id 4 = damage). Best effort: unknown
-- indices yield nil and are dropped.
local function read_self_awards()
    local MM = safe(sdk.find_type_definition, "app.MissionManager")
    local mgr = MM and safe(function() return sdk.get_managed_singleton("app.MissionManager") end)
    local dir = mgr and typecall("app.MissionManager", "get_QuestDirector", mgr)
    local param = dir and typecall("app.cQuestDirector", "get_Param", dir)
    if not param then return nil end
    local arr = typecall("app.cQuestFlowParam", "get_QuestAwardInfo", param)
    if not arr then return nil end
    local items = collect(arr, 48)
    local rec = { awards = {}, raw = {} }
    for i = 1, #items do
        local v = union_float(items[i])
        if v ~= nil then
            rec.raw[i - 1] = v
            if (i - 1) <= AWARD_MAX_ID then rec.awards[i - 1] = v end
        end
    end
    return rec
end

local function on_award_sync(args)
    if not config.enabled or state == nil then return end
    local sync, at = find_award_sync(args)
    if not sync then return end
    local idx = safe(function() return sdk.to_int64(args[at - 1]) end) or 0
    -- Diag: what does the award hook actually carry? Bounded samples of
    -- arg shapes plus the sync object's field list (one-time discovery).
    -- If anything here bears a name or character link, it becomes the
    -- ground-truth userIndex->identity map the HP path is missing.
    if state and state.diag_hook and #state.diag_hook < 8 then
        local nargs = safe(function() return #args end) or 0
        local entry = { idx = idx, nargs = nargs, argv = {} }
        for ai = 1, nargs do
            local a = args[ai]
            local mo = safe(function() return sdk.to_managed_object(a) end)
            entry.argv[#entry.argv + 1] = {
                i = ai,
                ptr = tostring(a),
                int = safe(function() return sdk.to_int64(a) end),
                type = mo and type_name(mo) or nil,
            }
        end
        state.diag_hook[#state.diag_hook + 1] = entry
    end
    if state and state.diag_sync_fields == nil then
        local td = safe(function() return sync:get_type_definition() end)
        local fields = {}
        for _, f in ipairs(safe(function() return td and td:get_fields() end) or {}) do
            local n = safe(function() return f:get_name() end)
            if n then fields[#fields + 1] = n end
        end
        state.diag_sync_fields = {
            type = safe(function() return td and td:get_full_name() end),
            fields = fields,
        }
    end
    local rec = read_award_sync(sync)
    rec.index = idx
    awards[idx + 1] = rec
    dlog("shared awards: idx=%d ids=%d", idx, (function() local n = 0 for _ in pairs(rec.awards) do n = n + 1 end return n end)())
end

-- Localized award names/explanations/units for ids 0..29 (cached once).
local award_meta_cache = nil
local function clean_text(s)
    if type(s) ~= "string" then return s end
    return (s:gsub("\r\n", " "):gsub("\n", " "))
end

local function get_award_meta()
    if award_meta_cache then return award_meta_cache end
    local QD = safe(sdk.find_type_definition, "app.QuestDef")
    local MU = safe(sdk.find_type_definition, "app.MessageUtil")
    local nameM = QD and safe(function() return QD:get_method("Name(app.QuestDef.AwardID)") end)
    local expM = QD and safe(function() return QD:get_method("Explain(app.QuestDef.AwardID)") end)
    local unitM = QD and safe(function() return QD:get_method("Unit(app.QuestDef.AwardID)") end)
    local textM = MU and safe(function() return MU:get_method("getText(System.Guid, System.Int32)") end)
    if not (nameM and textM) then return nil end
    local out = {}
    for id = 0, AWARD_MAX_ID do
        local g = safe(function() return nameM:call(nil, id) end)
        local name = g and safe(function() return textM:call(nil, g, 0) end)
        local eg = expM and safe(function() return expM:call(nil, id) end)
        local explain = eg and safe(function() return textM:call(nil, eg, 0) end)
        local unit = unitM and safe(function() return unitM:call(nil, id) end)
        out[#out + 1] = { id = id, name = clean_text(safe_str(name)),
                          explain = clean_text(safe_str(explain)), unit = unit }
    end
    award_meta_cache = out
    return out
end

-- ---------------------------------------------------------------------------
-- NPC / supporter hunters (CPU companions)
-- ---------------------------------------------------------------------------

local function obj_get(m, key)
    local td = safe(function() return m:get_type_definition() end)
    if td then
        local meth = safe(function() return td:get_method("get_" .. key .. "()") end)
        if meth then return safe(function() return meth:call(m) end) end
        for _, fname in ipairs({ key, "<" .. key .. ">k__BackingField" }) do
            local fld = safe(function() return td:get_field(fname) end)
            if fld then return safe(function() return fld:get_data(m) end) end
        end
    end
    return safe(function() return m[key] end)
end

local function collect_npc_members()
    local out = {}
    local NM = safe(sdk.find_type_definition, "app.NpcManager")
    local nm = NM and safe(function() return sdk.get_managed_singleton("app.NpcManager") end)
    if not nm then return out end
    local pm = typecall("app.NpcManager", "get_PartnerManager", nm)
    if not pm then return out end
    for _, meth in ipairs({ "getQuestMembers", "getManagedMembers" }) do
        for _, m in ipairs(collect(typecall("app.cNpcPartnerManager", meth, pm), 8)) do
            if m then out[#out + 1] = m end
        end
        if #out > 0 then break end
    end
    if #out == 0 then
        local list = safe(function() return pm:get_field("_PartnerList") end)
        for _, m in ipairs(collect(list, 8)) do
            if m then out[#out + 1] = m end
        end
    end
    return out
end

-- Support-hunter names by NpcID (app.HunterCharacter partner id). Mirrors
-- HunterPie's Npcs/Wilds table; unknown ids fall back to "NPC <id>".
local NPC_NAMES = {
    [4] = "Fabius", [6] = "Rosso", [9] = "Olivia", [12] = "Nadia",
    [15] = "Griffin", [17] = "Kai", [25] = "Mina", [27] = "Alessa",
    [29] = "Nightmist",
}

local function read_npc_players()
    local result = {}
    for _, m in ipairs(collect_npc_members()) do
        local npc_id = obj_get(m, "NpcID")
        local valid = obj_get(m, "Valid")
        local member_index = obj_get(m, "MemberIndex")
        if npc_id and valid ~= false and member_index ~= nil then
            result[#result + 1] = {
                name = NPC_NAMES[npc_id] or ("NPC " .. tostring(npc_id)),
                gear = nil,
                damages = {}, -- per-NPC damage not exposed via managed API
                is_supporter = true,
            }
        end
    end
    return result
end

-- ---------------------------------------------------------------------------
-- Self weapon name: EquipDataSetting._Weapon<Type>.get_Values()[id]._Name
-- Only the LOCAL player's weapon is resolved: findPlayerInfo_MemberIndex does
-- not line up with the UserInfoList order, so remote weapons come out swapped.
-- HunterPie owns per-player weapon classes; this is the local weapon's name.
-- ---------------------------------------------------------------------------

local WEAPON_FIELDS = { "_WeaponLongSword", "_WeaponShortSword", "_WeaponTwinSword",
    "_WeaponTachi", "_WeaponHammer", "_WeaponWhistle", "_WeaponLance", "_WeaponGunLance",
    "_WeaponSlashAxe", "_WeaponChargeAxe", "_WeaponRod", "_WeaponBow",
    "_WeaponHeavyBowgun", "_WeaponLightBowgun" }
local weapon_arrays = nil
local weapon_name_cache = {}

local function localized(guid)
    if guid == nil then return nil end
    local msg = safe(sdk.find_type_definition, "via.gui.message")
    local get = msg and safe(function() return msg:get_method("get(System.Guid)") end)
    return get and safe_str(safe(function() return get:call(nil, guid) end)) or nil
end

local function get_weapon_arrays()
    if weapon_arrays ~= nil then return weapon_arrays end
    weapon_arrays = {}
    local vdm = safe(function() return sdk.get_managed_singleton("app.VariousDataManager") end)
    local equipData = vdm and safe(function() return vdm._Setting._EquipDatas end)
    if equipData then
        for i, fname in ipairs(WEAPON_FIELDS) do
            local arr = safe(function() return equipData[fname] end)
            local list = {}
            if arr then
                list = collect(safe(function() return arr:call("get_Values") end), 400)
            end
            weapon_arrays[i - 1] = list
        end
    end
    return weapon_arrays
end

-- get_WeaponID() is a 0-based index into the type's weapon array in-quest;
-- the mod's array (collect) is 1-based, so resolve with list[id + 1] (this
-- fixes the off-by-one that showed "War Conga" as "War Bongo II"). Fall back
-- to list[id] so a trailing entry still resolves.
weapon_name = function(wtype, wid)
    if wtype == nil or wid == nil then return nil end
    local key = tostring(wtype) .. ":" .. tostring(wid)
    if weapon_name_cache[key] ~= nil then return weapon_name_cache[key] or nil end
    local list = get_weapon_arrays()[wtype]
    local entry = list and (list[wid + 1] or list[wid])
    if entry == nil and list then
        for _, e in ipairs(list) do
            local ix = safe(function() return e:get_field("_Index") end)
            if ix ~= nil and (ix == wid + 1 or ix == wid) then entry = e break end
        end
    end
    local name = entry and localized(safe(function() return entry:get_field("_Name") end))
    weapon_name_cache[key] = name or false
    return name
end

-- Calibration aid: names + _Index for the raw id and its two neighbours, so a
-- single hunt confirms which slot is the equipped weapon.
local function weapon_entry_probe(wtype, wid)
    local list = get_weapon_arrays()[wtype]
    if not list or wid == nil then return nil end
    local function info(pos)
        local e = list[pos]
        if not e then return nil end
        return { pos = pos,
                 index = safe(function() return e:get_field("_Index") end),
                 name = localized(safe(function() return e:get_field("_Name") end)) }
    end
    return { id = wid, minus1 = info(wid - 1), at = info(wid), plus1 = info(wid + 1) }
end

self_weapon_id = function()
    local pm = safe(function() return sdk.get_managed_singleton("app.PlayerManager") end)
    local info = pm and typecall("app.PlayerManager", "getMasterPlayer", pm)
    local ch = info and typecall("app.cPlayerManageInfo", "get_Character", info)
    return ch and typecall("app.HunterCharacter", "get_WeaponID", ch)
end

local function write_dump(dump)
    ensure_dir()
    local stamp = os.date("!%Y%m%d_%H%M%S", math.floor(state.finished or os.time()))
    local fname = state.hash .. "_" .. stamp .. ".json"
    -- preferred: absolute path next to this script
    if OUT_DIR then
        local f = safe(io.open, OUT_DIR .. "\\" .. fname, "w")
            or safe(io.open, OUT_DIR .. "/" .. fname, "w")
        if f then
            f:write(json.encode(dump))
            f:close()
            return OUT_DIR .. "\\" .. fname
        end
    end
    -- fallback: REFramework data dir
    json.dump_file(OUT_SUBDIR .. "/" .. fname, dump)
    return OUT_SUBDIR .. "/" .. fname
end

-- Quest result. The reward screen fires for failures too, so "the reward
-- screen opened" is not proof of a clear: read SuccessState (2 = clear,
-- 1 = leave, >=3 = failed) when the build exposes it, and fall back to the
-- time limit (time up) and cart limit (wipe).
local RESULT_HINTS = { "Result", "Success", "Fail", "Clear", "QuestState",
                       "Life" }

local function quest_result_probe()
    local probe = {}
    local mgr = safe(function()
        return sdk.get_managed_singleton("app.MissionManager") end)
    local dir = mgr and safe(function()
        return call_method(mgr, "get_QuestDirector") end)
    local aqd = mgr and safe(function()
        return call_method(mgr, "get_ActiveQuestData") end)
    local qm = safe(function()
        return sdk.get_managed_singleton("app.cQuestManager") end)
    local targets = { aqd = aqd, dir = dir, mgr = mgr, qm = qm }
    for key, obj in pairs(targets) do
        local td = obj and safe(function() return obj:get_type_definition() end)
        for _, m in ipairs(safe(function() return td and td:get_methods() end) or {}) do
            local n = safe(function() return m:get_name() end)
            local hit = false
            if n then
                for _, h in ipairs(RESULT_HINTS) do
                    if n:find(h) then hit = true break end
                end
            end
            if hit then
                local v = safe(function() return m:call(obj) end)
                if v ~= nil and (type(v) == "number" or type(v) == "boolean") then
                    probe[#probe + 1] = { obj = key, name = n,
                                          value = tostring(v) }
                end
            end
        end
    end
    return probe
end

local function interpret_result(probe)
    local ss, fs
    for _, p in ipairs(probe) do
        local v = tonumber(p.value)
        if v then
            if p.name:find("SuccessState") then ss = v end
            if p.name:find("FailureState") then fs = v end
        end
    end
    if ss == 2 then return "success" end
    if ss == 1 then return "quit" end
    if ss and ss >= 3 then return "fail" end
    if fs and fs > 0 then return "fail" end
    return nil
end

local function finish_session()
    if not config.enabled or state == nil or state.finished then return end
    state.finished = utc_now()
    state.users = quest_users() -- refresh names if needed
    if #state.em_ids == 0 then state.em_ids = get_active_em_ids() end -- em set may fill late

    local started = state.started
    local finished = state.finished
    local result_probe = quest_result_probe()
    local result = interpret_result(result_probe)
    local elapsed = (type(started) == "number" and type(finished) == "number")
        and (finished - started) or nil
    if result == nil then
        -- getActiveTimeLimit units are not documented: values <= 120 are
        -- minutes (15/25/50), larger ones are seconds (900/1500/3000).
        local limit = state.meta and state.meta.time_limit
        local limit_s = nil
        if type(limit) == "number" and limit > 0 then
            limit_s = limit <= 120 and limit * 60 or limit
        end
        if limit_s and elapsed and elapsed >= limit_s - 5 then
            result = "fail"  -- time up
        else
            result = "success"
        end
    end

    -- awards: multiplayer fills `awards` via the shared sync (per userIndex);
    -- solo falls back to the self player's get_QuestAwardInfo().
    local self_awards = read_self_awards()
    -- Local weapon name read at the reward screen (the older build did this
    -- and it looked stable); keep the quest-start reading for calibration.
    local self_wid = self_weapon_id()
    local self_name = weapon_name(state.self_wtype, self_wid)
    local self_name_start = weapon_name(state.self_wtype, state.self_wid_start)

    local function awards_list_for(rec)
        if not rec or not rec.awards then return nil end
        local ids = {}
        for id in pairs(rec.awards) do ids[#ids + 1] = id end
        table.sort(ids)
        local out = {}
        for _, id in ipairs(ids) do
            out[#out + 1] = { id = id, count = rec.awards[id], channels = (id == 0) and rec.channels or nil }
        end
        return out
    end

    -- Map HP series to roster entries. `php` is keyed by control slot;
    -- the compact user list position is NOT that slot (an SOS player can sit at
    -- slot 6 while being list position 1), so position `i` is only a last
    -- resort. Order: observed name on the series, then stable slot/index,
    -- then position. Trying `i` first swaps two hunters' HP (e.g. one
    -- hunter shown with another's cart).
    local hp_assigned = {}
    local hp_used = {}
    local missing = {}
    local function has_samples(key)
        local rec = state.php and state.php[key]
        return rec ~= nil and #rec.samples > 0
    end
    local function hp_name(key)
        local rec = state.php and state.php[key]
        return rec and rec.name or nil
    end
    for i = 0, 7 do
        local u = state.users and state.users[i]
        if u and u.name then
            local key
            -- 1) series whose observed name matches this roster entry
            -- (checked in stable-key order so the result is deterministic).
            for _, k in ipairs({ u.slot, u.idx, i }) do
                if k ~= nil and not hp_used[k] then
                    local rec = state.php and state.php[k]
                    if rec and #rec.samples > 0 and rec.name == u.name then
                        key = k
                        break
                    end
                end
            end
            -- 2) stable identity: control slot, then user index.
            if key == nil then
                for _, k in ipairs({ u.slot, u.idx }) do
                    if k ~= nil and not hp_used[k] and has_samples(k) then
                        key = k
                        break
                    end
                end
            end
            -- 3) list position (only when slot/idx are unknown).
            if key == nil and not hp_used[i] and has_samples(i) then
                -- Don't steal a series another roster entry already names.
                local taken = false
                for j = 0, 7 do
                    local o = state.users and state.users[j]
                    if j ~= i and o and o.name and hp_name(i) == o.name then
                        taken = true
                        break
                    end
                end
                if not taken then key = i end
            end
            if key == nil and not hp_used[u.name] and has_samples(u.name) then
                key = u.name
            end
            if key ~= nil then
                hp_used[key] = true
                hp_assigned[i] = key
            else
                missing[#missing + 1] = i
            end
        end
    end
    local unused_hp = {}
    for k, rec in pairs(state.php or {}) do
        if not hp_used[k] and rec and #rec.samples > 0 then
            unused_hp[#unused_hp + 1] = k
        end
    end
    if #missing == 1 and #unused_hp == 1 then
        hp_assigned[missing[1]] = unused_hp[1]
    end
    -- General rescue: a series keyed by a stale/garbage slot still remembers
    -- the name observed while sampling it, so match leftovers by name before
    -- giving up. Key skew then costs nothing and samples always land.
    for _, mi in ipairs(missing) do
        if hp_assigned[mi] == nil then
            local u = state.users and state.users[mi]
            for ui = #unused_hp, 1, -1 do
                local k = unused_hp[ui]
                local rec = state.php and state.php[k]
                if u and u.name and rec and rec.name == u.name
                    and not hp_used[k] then
                    hp_assigned[mi] = k
                    hp_used[k] = true
                    table.remove(unused_hp, ui)
                    break
                end
            end
        end
    end

    -- players: name + damage + awards (weapons come from HunterPie)
    -- awards[] is keyed by USER INDEX (the sync hook's userIndex), not by
    -- compact list position, so look up (slot/idx)+1 — never i+1 alone — or
    -- damage/awards swap the same way HP did.
    local players = {}
    local n_players = 0
    for i = 0, 7 do
        local u = state.users[i]
        if u and u.name then
            local rec = awards[(u.idx or u.slot or i) + 1]
                or awards[(u.slot or i) + 1]
                or awards[i + 1]
            if u.is_self and rec == nil then rec = self_awards end
            local damage = 0
            if rec and rec.awards and rec.awards[DAMAGE_AWARD_ID] then
                damage = rec.awards[DAMAGE_AWARD_ID]
            end
            players[#players + 1] = {
                name = u.name,
                weapon_name = u.is_self and self_name or nil,
                gear = nil,
                damages = { { damage = damage, dealt_at = iso(finished) } },
                awards = awards_list_for(rec),
                health_steps = hp_assigned[i]
                    and php_health_steps(hp_assigned[i]) or nil,
                is_hunterpie_user = false,
            }
            n_players = n_players + 1
        end
    end
    -- CPU companions: flag as supporters so the dashboard excludes them from
    -- synergy/leaderboards but keeps the roster complete.
    local npc_players = read_npc_players()
    for _, p in ipairs(npc_players) do
        players[#players + 1] = p
        n_players = n_players + 1
    end
    if n_players == 0 then
        config.last_status = "no players captured; dump skipped"
        dlog(config.last_status)
        state = nil
        return
    end

    -- monsters: id from active em set; HP curve per boss index
    local monsters = {}
    for bi, enemy_id in ipairs(state.em_ids) do
        local steps = {}
        for _, s in ipairs(state.hp[bi] or {}) do
            steps[#steps + 1] = { percentage = s.norm, time = iso(s.t) }
        end
        monsters[#monsters + 1] = {
            id = enemy_id,
            variant = nil,
            max_health = state.max_hp or 0,
            crown = nil,
            hunt_started_at = iso(started),
            hunt_finished_at = iso(finished),
            hunt_type = 1,
            health_steps = steps,
        }
    end
    if #monsters == 0 then
        config.last_status = "no monsters (no active em set); dump skipped"
        dlog(config.last_status)
        state = nil
        return
    end

    local dump = {
        game_type = GAME_TYPE,
        mod_version = VERSION,
        started_at = iso(started),
        finished_at = iso(finished),
        uploaded_at = iso(utc_now()),
        quest = {
            id = state.meta.level,
            type = 0,
            result = result,
            cleared = result == "success",
            time_limit = state.meta.time_limit,
            elapsed = elapsed,
            result_probe = result_probe,
            deaths = 0,
            max_deaths = state.meta.max_deaths or 0,
            level = state.meta.level or 0,
            stars = nil,
        },
        players = players,
        monsters = monsters,
        awards_meta = get_award_meta(),
        mod_debug = party_debug(),
        source = "reframework",
        -- calibration aid: raw self weapon ids + resolved names at both ends
        self_weapon = { type = state.self_wtype,
                        id_start = state.self_wid_start,
                        name_start = self_name_start,
                        id_finish = self_wid, name_finish = self_name,
                        probe = weapon_entry_probe(state.self_wtype, self_wid) },
        hash = state.hash,
    }

    local where = safe(write_dump, dump)
    config.last_status = where and ("wrote " .. tostring(where)) or "write failed"
    log.info("[HuntDumper] " .. config.last_status)
    state = nil
end

-- ---------------------------------------------------------------------------
-- hooks
-- ---------------------------------------------------------------------------

local function register_hooks()
    -- quest start
    safe(function()
        local t = sdk.find_type_definition("app.cQuestPlaying")
        local m = t:get_method("enter()")
        sdk.hook(m, function() begin_session() end, nil)
    end)

    -- quest reward (success)
    safe(function()
        local t = sdk.find_type_definition("app.cQuestReward")
        local m = t:get_method("enter()")
        sdk.hook(m, function() finish_session() end, nil)
    end)

    -- multiplayer: per-player damage arrives via the shared award sync.
    safe(function()
        local t = sdk.find_type_definition("app.cQuestFlowParam")
        local m = t:get_method("setSharedQuestAwardInfo")
        if m then sdk.hook(m, function(args) on_award_sync(args) end, nil) end
    end)

    -- Load-time guard: a helper that is nil only fails when called at runtime
-- (a missing read_instanced_hp once cost us a whole debug cycle), so shout
-- about it as soon as the script loads.
local REQUIRED_HELPERS = {
    read_instanced_hp = read_instanced_hp,
    character_of = character_of,
    health_of = health_of,
    record_hp = record_hp,
    poll_party_hp = poll_party_hp,
    php_health_steps = php_health_steps,
}
for name, fn in pairs(REQUIRED_HELPERS) do
    if type(fn) ~= "function" then
        log.error("[HuntDumper] missing helper at load: " .. name)
    end
end

re.on_frame(function() safe(poll) end)
end

-- ---------------------------------------------------------------------------
-- UI
-- ---------------------------------------------------------------------------

load_config()
register_hooks()

re.on_draw_ui(function()
    if imgui.tree_node("HuntDumper") then
        imgui.text("v" .. VERSION .. "  (totals + HP curve + awards + party HP)")
        imgui.separator()
        local changed
        changed, config.enabled = imgui.checkbox("Enabled", config.enabled)
        if changed then save_config() end
        changed, config.debug = imgui.checkbox("Debug log", config.debug)
        if changed then save_config() end
        if imgui.button("Open output folder") then
            if OUT_DIR then safe(os.execute, 'explorer "' .. OUT_DIR .. '"') end
        end
        imgui.separator()
        imgui.text("out: " .. tostring(OUT_DIR or "(unknown)"))
        imgui.text("status: " .. tostring(config.last_status))
        if state then
            imgui.text(string.format("in quest: em_ids=%d hp_samples=%d",
                #(state.em_ids or {}), #((state.hp or {})[1] or {})))
        end
        imgui.tree_pop()
    end
end)

log.info("[HuntDumper] loaded v" .. VERSION .. " out=" .. tostring(OUT_DIR))
