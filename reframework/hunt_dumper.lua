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

local VERSION = "0.9.2"
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
    return os.date("!%Y-%m-%dT%H:%M:%S", math.floor(epoch)) .. "Z"
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
            out[i - 1] = {
                name = safe_str(safe(function() return u:get_PlName() end)),
                short = safe_str(safe(function() return u:get_ShortHunterId() end)),
                is_self = safe(function() return u:get_IsSelf() end),
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
        hp = {},          -- [bossIndex] = { {t, norm}, ... }
        max_hp = nil,
        last_poll = 0,
        finished = false,
        self_wtype = self_wtype,
        self_wid_start = self_wid_start,
    }
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

-- get_WeaponID() is a 1-based position into the type's weapon array (NOT a
-- 0-based index and NOT the entry's _Index); resolve with list[id].
weapon_name = function(wtype, wid)
    if wtype == nil or wid == nil then return nil end
    local key = tostring(wtype) .. ":" .. tostring(wid)
    if weapon_name_cache[key] ~= nil then return weapon_name_cache[key] or nil end
    local list = get_weapon_arrays()[wtype]
    local entry = list and list[wid]
    if entry == nil and list then
        for _, e in ipairs(list) do
            local ix = safe(function() return e:get_field("_Index") end)
            if ix ~= nil and ix == wid then entry = e break end
        end
    end
    local name = entry and localized(safe(function() return entry:get_field("_Name") end))
    weapon_name_cache[key] = name or false
    return name
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

local function finish_session()
    if not config.enabled or state == nil or state.finished then return end
    state.finished = utc_now()
    state.users = quest_users() -- refresh names if needed
    if #state.em_ids == 0 then state.em_ids = get_active_em_ids() end -- em set may fill late

    local started = state.started
    local finished = state.finished

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

    -- players: name + damage + awards (weapons come from HunterPie)
    local players = {}
    local n_players = 0
    for i = 0, 3 do
        local u = state.users[i]
        if u and u.name then
            local rec = awards[i + 1]
            if u.is_self and rec == nil then rec = self_awards end
            local damage = 0
            if rec and rec.awards and rec.awards[DAMAGE_AWARD_ID] then
                damage = rec.awards[DAMAGE_AWARD_ID]
            end
            players[#players + 1] = {
                name = u.name,
                short_hunter_id = u.short,
                weapon_name = u.is_self and self_name or nil,
                gear = nil,
                damages = { { damage = damage, dealt_at = iso(finished) } },
                awards = awards_list_for(rec),
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
        started_at = iso(started),
        finished_at = iso(finished),
        uploaded_at = iso(utc_now()),
        quest = {
            id = state.meta.level,
            type = 0,
            deaths = 0,
            max_deaths = state.meta.max_deaths or 0,
            level = state.meta.level or 0,
            stars = nil,
        },
        players = players,
        monsters = monsters,
        awards_meta = get_award_meta(),
        source = "reframework",
        -- calibration aid: raw self weapon ids + resolved names at both ends
        self_weapon = { type = state.self_wtype,
                        id_start = state.self_wid_start,
                        name_start = self_name_start,
                        id_finish = self_wid, name_finish = self_name },
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

    re.on_frame(function() safe(poll) end)
end

-- ---------------------------------------------------------------------------
-- UI
-- ---------------------------------------------------------------------------

load_config()
register_hooks()

re.on_draw_ui(function()
    if imgui.tree_node("HuntDumper") then
        imgui.text("v" .. VERSION .. "  (totals + HP curve + awards)")
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
