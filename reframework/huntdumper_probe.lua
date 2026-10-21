--
-- HuntDumper R0 probe  (temporary discovery script — delete after R0)
--
-- Purpose: find out what MH Wilds data REFramework can expose, so the
-- permanent hunt_dumper.lua can be written against real type/method names.
--
-- Usage:
--   1. Launch the game with REFramework.
--   2. Open the REFramework menu (default key) -> "HuntDumper Probe (R0)".
--   3. Click "Dump types" (works anywhere), then load into a quest and click
--      "Sample runtime" (best: mid-hunt with monsters alive + a couple of
--      hits landed).
--   4. Results are written to:
--        reframework/data/huntdumper_probe_types.json
--        reframework/data/huntdumper_probe_runtime.json
--
-- The probe never throws into the game: every SDK call is pcall-guarded.
--

local re = re
local sdk = sdk
local json = json
local log = log
local imgui = imgui

local PROBE_VERSION = 4
local OUT_TYPES = "huntdumper_probe_types.json"
local OUT_RUNTIME = "huntdumper_probe_runtime.json"
local OUT_NPC = "huntdumper_probe_npc.json"
local OUT_BUFFS = "huntdumper_probe_buffs.json"
local MAX_STR = 200

local lastStatus = "(idle)"

local function safe(fn, ...)
    local ok, res = pcall(fn, ...)
    if ok then
        return res
    end
    return nil
end

local function safe_str(v)
    if v == nil then return nil end
    local t = type(v)
    if t == "string" then
        if #v > MAX_STR then return v:sub(1, MAX_STR) .. "..." end
        return v
    end
    if t == "number" or t == "boolean" then return v end
    return tostring(v)
end

-- Call a zero-arg method declared on `typeName` against instance `obj`
-- (handles subclasses). Tries "name()" then bare "name".
local function typecall(typeName, methodName, obj)
    local td = safe(sdk.find_type_definition, typeName)
    if not td then return nil end
    local m = safe(function() return td:get_method(methodName .. "()") end)
        or safe(function() return td:get_method(methodName) end)
    if not m then return nil end
    return safe(function() return m:call(obj) end)
end

-- Static enum/const name -> value for a type.
local function enum_values(typeName)
    local td = safe(sdk.find_type_definition, typeName)
    if not td then return nil end
    local fields = safe(function() return td:get_fields() end)
    local out = {}
    if fields then
        for _, f in ipairs(fields) do
            if safe(function() return f:is_static() end) then
                local n = safe(function() return f:get_name() end)
                out[n] = safe_str(safe(function() return f:get_data(nil) end))
            end
        end
    end
    return out
end

-- Localized text for a System.Guid-ish handle.
local function localized(guid)
    if guid == nil then return nil end
    local msg = safe(sdk.find_type_definition, "via.gui.message")
    local get = msg and safe(function() return msg:get_method("get(System.Guid)") end)
    if not get then return nil end
    return safe_str(safe(function() return get:call(nil, guid) end))
end

-- Read an instance field by name using the field's get_data (works where
-- obj:get_field() returns nil). Static fields are read with nil instance.
local function field_value(obj, fieldName)
    if obj == nil then return nil end
    local td = safe(function() return obj:get_type_definition() end)
    if not td then return nil end
    local fields = safe(function() return td:get_fields() end)
    if not fields then return nil end
    for _, f in ipairs(fields) do
        local n = safe(function() return f:get_name() end)
        if n == fieldName then
            local is_static = safe(function() return f:is_static() end)
            return safe(function() return f:get_data(is_static and nil or obj) end)
        end
    end
    return nil
end

-- Read a boxed System.Single element (arr[i]) -> number.
local function boxed_float(elem)
    if elem == nil then return nil end
    local v = field_value(elem, "m_value")
    if type(v) == "number" then return v end
    if type(elem) == "number" then return elem end
    return nil
end

-- ---------------------------------------------------------------------------
-- Static type reflection
-- ---------------------------------------------------------------------------

local TYPES = {
    -- quest / flow
    "app.QuestUtil", "app.QuestDef", "app.cQuestDef", "app.cQuestDirector",
    "app.cQuestPlaying", "app.cQuestStart", "app.cQuestClearEnd",
    "app.cQuestReward", "app.cQuestFlowParam", "app.cQuestAwardSync",
    "app.cActiveQuestData", "app.MissionManager",
    -- enemies / monsters
    "app.EnemyManager", "app.EnemyCharacter", "app.EnemyDef",
    "app.TargetAccessKeyUtil", "app.TARGET_ACCESS_KEY",
    -- players / network
    "app.PlayerManager", "app.PlayerManageInfo", "app.cPlayerManageInfo",
    "app.HunterCharacter", "app.Weapon", "app.WeaponDef", "app.WeaponUtil",
    "app.NetworkManager", "app.Net_UserInfoManager", "app.UserInfoManager",
    "app.Net_UserInfo", "app.Net_UserInfoList", "app.MessageUtil",
    -- enemy context chain (identity of a live boss)
    "app.cEnemyContextHolder", "app.EnemyContext", "app.cEmContext",
    "app.cEnemy", "app.Enemy",
    -- NPC / supporter hunters
    "app.NpcManager", "app.cNpcPartnerManageControl", "app.NpcPartnerManageInfo",
    "app.NpcPartnerManageControl", "app.OtomoManager", "app.OtomoCharacter",
    "app.cNpcPlacementInfo", "app.NpcPlacementInfo", "app.cNpcCreateArg",
    "app.NpcCreateArg", "app.cNpcCreationInfo", "app.NpcCreationInfo",
    "app.cNpcPartnerManager", "app.cNpcHunterManageControl", "app.cHunterCreateInfo",
    "app.cNpcManageInfo", "app.cNpcContextHolder", "app.cNpcCatalogHolder",
    "app.cNpcPartnerCreateArg", "app.cNpcPartnerNetMemberInfo",
    -- NPC name resolution candidates
    "app.NpcManagerSetting", "app.NpcPartnerData", "app.cNpcPartnerContext",
    "app.cNpcContext", "app.cCharacterContext", "app.NpcController",
    "app.NpcCharacterCore", "app.NpcAccessor", "app.NpcResidentPackage",
    "app.NpcDef", "app.NpcEnumDefine", "app.NpcDefine", "app.NpcData",
    -- weapon identity (name resolution)
    "app.SaveDataManager", "app.savedata.cEquipWork", "app.savedata.cSaveData",
    "app.user_data.WeaponData", "app.user_data.WeaponData.cData",
    "app.cEquipBox", "app.WeaponEnumData", "app.cWeaponTree",
    -- damage / health candidates
    "app.DamageManager", "app.cDamageManager", "app.DamageInfo",
    "app.cDamageInfo", "app.cHunterDamageManager", "app.cEnemyDamage",
    "app.EnemyDamageInfo", "app.cAttackInfo", "app.AttackInfo",
    "app.cPlayerDamage", "app.cMonsterDamage", "app.MonsterDamage",
    "app.cHealthManager", "app.cEnemyHealth", "app.cHitDamageInfo",
    "app.cDamage", "app.cEnemyDamageInfo",
    -- buff / abnormality / status candidates
    "app.cStatusManager", "app.StatusManager",
    "app.cBuffManager", "app.BuffManager",
    "app.cAbnormalityManager", "app.AbnormalityManager",
    "app.cPlayerStatus", "app.PlayerStatus",
    "app.cHunterHealth", "app.HunterHealth",
    "app.cStatusBase", "app.StatusBase",
    "app.cStatusData", "app.StatusData",
    "app.StatusKind", "app.cStatusKind",
    "app.BuffKind", "app.cBuffKind",
    "app.AbnormalityKind", "app.cAbnormalityKind",
    "app.cConsumableManager", "app.ConsumableManager",
    "app.cSkillManager", "app.SkillManager",
    "app.cDebuffManager", "app.DebuffManager",
    "app.cSongManager", "app.SongManager",
    "app.cOrchestraManager", "app.OrchestraManager",
    "app.cOtomoSongManager", "app.OtomoSongManager",
}

local function describe_field(f)
    return {
        name = safe(function() return f:get_name() end),
        type = safe(function() return f:get_type():get_name() end),
        static = safe(function() return f:is_static() end),
    }
end

local function describe_method(m)
    return {
        name = safe(function() return m:get_name() end),
        full = safe(function() return m:get_full_name() end),
        ret = safe(function() return m:get_return_type():get_name() end),
    }
end

local function dump_type(typeName)
    local td = safe(sdk.find_type_definition, typeName)
    local entry = { name = typeName, exists = td ~= nil }
    if not td then
        return entry
    end
    entry.full_name = safe(function() return td:get_full_name() end)

    local fields = safe(function() return td:get_fields() end)
    if fields then
        entry.fields = {}
        for _, f in ipairs(fields) do
            entry.fields[#entry.fields + 1] = describe_field(f)
        end
    end

    local methods = safe(function() return td:get_methods() end)
    if methods then
        entry.methods = {}
        for _, m in ipairs(methods) do
            entry.methods[#entry.methods + 1] = describe_method(m)
        end
    end
    return entry
end

local function dump_types()
    local out = { probe_version = PROBE_VERSION, kinds = {} }
    for _, name in ipairs(TYPES) do
        out.kinds[#out.kinds + 1] = dump_type(name)
    end
    json.dump_file(OUT_TYPES, out)
    local n = 0
    for _, e in ipairs(out.kinds) do
        if e.exists then n = n + 1 end
    end
    lastStatus = string.format("types: %d/%d exist -> %s", n, #TYPES, OUT_TYPES)
    log.info("[HuntDumperProbe] " .. lastStatus)
    return out
end

-- ---------------------------------------------------------------------------
-- Runtime sampling
-- ---------------------------------------------------------------------------

-- Read every field of a live object (pcall-guarded per field).
local function sample_instance(obj, maxFields)
    if obj == nil then return nil end
    local td = safe(function() return obj:get_type_definition() end)
    local tname = safe(function() return td:get_full_name() end)
    local out = { type = tname, fields = {}, methods = {} }
    if not td then return out end

    local fields = safe(function() return td:get_fields() end)
    if fields then
        local i = 0
        for _, f in ipairs(fields) do
            i = i + 1
            if maxFields and i > maxFields then break end
            local name = safe(function() return f:get_name() end)
            local is_static = safe(function() return f:is_static() end)
            local val = safe(function() return f:get_data(is_static and nil or obj) end)
            out.fields[#out.fields + 1] = { name = name, value = safe_str(val) }
        end
    end

    -- getters that look like HP/health/life, 0-arg only
    local methods = safe(function() return td:get_methods() end)
    if methods then
        for _, m in ipairs(methods) do
            local fname = safe(function() return m:get_full_name() end) or ""
            local low = fname:lower()
            if fname:find("get_") and fname:find("%(%)$") and
               (low:find("hp") or low:find("health") or low:find("life")) then
                local v = safe(function() return m:call(obj) end)
                out.methods[#out.methods + 1] = { name = fname, value = safe_str(v) }
            end
        end
    end
    return out
end

-- Iterate a C# list/array, returns a Lua array.
-- C# List<T>: has get_Count / get_Item (methods). C# arrays support 0-based [i].
local function collect(list, maxItems)
    local out = {}
    if list == nil then return out end

    local cntMethod = safe(function() return list.get_Count end)
    local itemMethod = safe(function() return list.get_Item end)
    if cntMethod ~= nil and itemMethod ~= nil then
        local n = safe(function() return cntMethod:call(list) end) or 0
        if maxItems and n > maxItems then n = maxItems end
        for i = 0, n - 1 do
            out[#out + 1] = safe(function() return itemMethod:call(list, i) end)
        end
        return out
    end

    -- C# array: 0-based indexing
    for i = 0, 64 do
        if maxItems and i >= maxItems then break end
        local v = safe(function() return list[i] end)
        if v == nil then break end
        out[#out + 1] = v
    end
    return out
end

local function sample_enemies(out)
    out.bosses = {}
    local QuestUtil = safe(sdk.find_type_definition, "app.QuestUtil")
    if not QuestUtil then return end
    local getList = safe(function() return QuestUtil:get_method("getActiveQuestTargetBossList()") end)
    if not getList then return end
    local keys = safe(function() return getList:call(nil) end)
    if keys == nil then
        out.bosses_error = "getActiveQuestTargetBossList() returned nil (not in a quest?)"
        return
    end
    local keyList = collect(keys, 8)

    local Taku = safe(sdk.find_type_definition, "app.TargetAccessKeyUtil")
    local getEnemy = Taku and safe(function() return Taku:get_method("getEnemyCharacter(app.TARGET_ACCESS_KEY, System.Boolean)") end)
    for i, key in ipairs(keyList) do
        local enemy = getEnemy and safe(function() return getEnemy:call(nil, key, true) end)
        out.bosses[#out.bosses + 1] = {
            index = i - 1,
            enemy = sample_instance(enemy, 80),
        }
    end
end

local function sample_players(out)
    out.players = {}
    local NM = safe(sdk.find_type_definition, "app.NetworkManager")
    local nm = NM and safe(function() return sdk.get_managed_singleton("app.NetworkManager") end)
    if not nm then
        out.players_error = "NetworkManager singleton not found"
        return
    end
    local uim = safe(function() return nm:call("get_UserInfoManager") end)
        or safe(function() return nm:get_field("<UserInfoManager>k__BackingField") end)
    if not uim then
        out.players_error = "UserInfoManager not found"
        return
    end
    -- SESSION_TYPE.QUEST == 2
    local num = safe(function() return uim:getMemberNum(2) end) or 0
    out.player_count = num
    local uil = safe(function() return uim:getUserInfoList(2) end)
    local arr = uil and safe(function() return uil._ListInfo end)
    local users = collect(arr, 8)
    for i, u in ipairs(users) do
        if u then
            out.players[#out.players + 1] = {
                index = i - 1,
                name = safe_str(safe(function() return u:get_PlName() end)),
                short = safe_str(safe(function() return u:get_ShortHunterId() end)),
                is_self = safe(function() return u:get_IsSelf() end),
                info = sample_instance(u, 40),
            }
        end
    end
end

local function sample_quest(out)
    local MM = safe(sdk.find_type_definition, "app.MissionManager")
    local mgr = MM and safe(function() return sdk.get_managed_singleton("app.MissionManager") end)
    if mgr then
        out.quest_playing = safe(function() return mgr:call("get_IsPlayingQuest()") end)
        out.quest_active = safe(function() return mgr:call("get_IsActiveQuest()") end)
        local dir = safe(function() return mgr:call("get_QuestDirector()") end)
        if dir then
            out.quest_elapsed = safe(function() return dir:call("get_QuestElapsedTime()") end)
            out.quest_time_limit = safe(function() return dir:call("getActiveTimeLimit()") end)
            out.quest_started = safe(function() return dir:call("get_QuestStartedTime()") end)
            out.quest_director = sample_instance(dir, 40)
        end
    end
    -- utc time helper
    local QU = safe(sdk.find_type_definition, "app.QuestUtil")
    local getTime = QU and safe(function() return QU:get_method("getUTCTime()") end)
    out.utc_time = getTime and safe(function() return getTime:call(nil) end) or nil
end

local function sample_runtime()
    local out = { probe_version = PROBE_VERSION }
    sample_quest(out)
    sample_enemies(out)
    sample_players(out)
    json.dump_file(OUT_RUNTIME, out)
    lastStatus = string.format("runtime: %d bosses, %d players -> %s",
        #(out.bosses or {}), #(out.players or {}), OUT_RUNTIME)
    log.info("[HuntDumperProbe] " .. lastStatus)
    return out
end

-- ---------------------------------------------------------------------------
-- Deep runtime sample (v2): quest identity, boss HP, party weapons, enums
-- ---------------------------------------------------------------------------

local function sample_quest_data(out)
    out.quest = {}
    local MM = safe(sdk.find_type_definition, "app.MissionManager")
    local mgr = MM and safe(function() return sdk.get_managed_singleton("app.MissionManager") end)
    if not mgr then out.quest.error = "no MissionManager" return end

    local aqd = typecall("app.MissionManager", "get_ActiveQuestData", mgr)
    out.quest.has_active_quest_data = aqd ~= nil
    if aqd then
        out.quest.target_em_id = typecall("app.cActiveQuestData", "getTargetEmId", aqd)
        out.quest.target_em_role_id = typecall("app.cActiveQuestData", "getTargetEmRoleId", aqd)
        out.quest.target_em_legendary_id = typecall("app.cActiveQuestData", "getTargetEmLegendaryId", aqd)
        out.quest.target_em_difficulty_rank = typecall("app.cActiveQuestData", "getTargetEmDifficulityRank", aqd)
        out.quest.target_em_difficulty_grade = typecall("app.cActiveQuestData", "getTargetEmDifficulityGrade", aqd)
        out.quest.quest_lv = typecall("app.cActiveQuestData", "getQuestLv", aqd)
        out.quest.quest_life = typecall("app.cActiveQuestData", "getQuestLife", aqd)
        out.quest.time_limit = typecall("app.cActiveQuestData", "getTimeLimit", aqd)
        out.quest.reward_money = typecall("app.cActiveQuestData", "getRewardMoney", aqd)
        out.quest.is_capture = typecall("app.cActiveQuestData", "isClearConditionCapture", aqd)
        out.quest.is_kill = typecall("app.cActiveQuestData", "isClearConditionKill", aqd)
        out.quest.is_target_boss = typecall("app.cActiveQuestData", "isTargetBoss", aqd)
        out.quest.is_arena = typecall("app.cActiveQuestData", "isArenaQuest", aqd)
        -- monster name for the target em id (localized)
        local id = out.quest.target_em_id
        if id ~= nil then
            local EnemyDef = safe(sdk.find_type_definition, "app.EnemyDef")
            local nameM = EnemyDef and safe(function()
                return EnemyDef:get_method("EnemyName(app.EnemyDef.ID)")
            end)
            if nameM then
                out.quest.target_name_guid_text = localized(safe(function() return nameM:call(nil, id) end))
            end
        end
    end

    -- QuestUtil target text
    local QU = safe(sdk.find_type_definition, "app.QuestUtil")
    if QU then
        local gt = safe(function() return QU:get_method("getTargetText()") end)
        if gt then out.quest.target_text = safe_str(safe(function() return gt:call(nil) end)) end
        local gl = safe(function() return QU:get_method("getActiveQuestTargetBossList()") end)
        out.quest.boss_list_present = (gl and safe(function() return gl:call(nil) end)) ~= nil
    end

    -- QuestDirector extras
    local dir = typecall("app.MissionManager", "get_QuestDirector", mgr)
    if dir then
        out.quest.director_active_lv = typecall("app.cQuestDirector", "getActiveQuestLv", dir)
        out.quest.director_time_limit = typecall("app.cQuestDirector", "getActiveTimeLimit", dir)
        out.quest.director_started_time = typecall("app.cQuestDirector", "get_QuestStartedTime", dir)
        local qd = typecall("app.cQuestDirector", "get_QuestData", dir)
        out.quest.director_has_quest_data = qd ~= nil
    end

    -- QuestFlowParam weapon type at quest start
    if dir then
        local param = typecall("app.cQuestDirector", "get_Param", dir)
        if param then
            out.quest.start_weapon_type = typecall("app.cQuestFlowParam", "get_QuestStartWeaponType", param)
            out.quest.start_reserve_weapon_type = typecall("app.cQuestFlowParam", "get_QuestStartReserveWeaponType", param)
        end
    end
end

local function sample_boss_health(out)
    out.boss_health = {}
    local QuestUtil = safe(sdk.find_type_definition, "app.QuestUtil")
    local getList = QuestUtil and safe(function() return QuestUtil:get_method("getActiveQuestTargetBossList()") end)
    local keys = getList and safe(function() return getList:call(nil) end)
    if keys == nil then out.boss_health_error = "no boss list" return end
    local Taku = safe(sdk.find_type_definition, "app.TargetAccessKeyUtil")
    local getEnemy = Taku and safe(function()
        return Taku:get_method("getEnemyCharacter(app.TARGET_ACCESS_KEY, System.Boolean)")
    end)
    for i, key in ipairs(collect(keys, 8)) do
        local enemy = getEnemy and safe(function() return getEnemy:call(nil, key, true) end)
        local entry = { index = i - 1 }
        if enemy then
            entry.type = safe_str(safe(function() return enemy:get_type_definition():get_full_name() end))
            entry.health = typecall("app.EnemyCharacter", "get_HealthMgr", enemy)
            local hm = entry.health
            if hm then
                entry.hp = typecall("app.cHealthManager", "get_Health", hm)
                entry.max_hp = typecall("app.cHealthManager", "get_MaxHealth", hm)
                entry.hp_norm = typecall("app.cHealthManager", "get_HealthNormalized", hm)
            end
            entry.health = nil
            -- try to reach identity via the enemy context chain
            local ctx = safe(function() return enemy:get_field("_Context") end)
            if ctx then
                entry.context_type = safe_str(safe(function() return ctx:get_type_definition():get_full_name() end))
                entry.context_fields = sample_instance(ctx, 30)
            end
        end
        out.boss_health[#out.boss_health + 1] = entry
    end
end

-- v3: reach the live boss's identity via the enemy context chain, and the
-- quest's active em-set ids.
local function typecall1(typeName, methodName, obj, arg)
    local td = safe(sdk.find_type_definition, typeName)
    if not td then return nil end
    local m = safe(function() return td:get_method(methodName .. "(System.Int32)") end)
        or safe(function() return td:get_method(methodName .. "(System.UInt32)") end)
        or safe(function() return td:get_method(methodName .. "()") end)
        or safe(function() return td:get_method(methodName) end)
    if not m then return nil end
    return safe(function() return m:call(obj, arg) end)
end

local function sample_em_ids(out)
    out.em_ids = {}
    local QU = safe(sdk.find_type_definition, "app.QuestUtil")
    local getList = QU and safe(function() return QU:get_method("getActiveQuestTargetBossList()") end)
    local keys = getList and safe(function() return getList:call(nil) end)
    if keys == nil then out.em_ids.error = "no boss list" return end
    local Taku = safe(sdk.find_type_definition, "app.TargetAccessKeyUtil")
    local getEnemy = Taku and safe(function()
        return Taku:get_method("getEnemyCharacter(app.TARGET_ACCESS_KEY, System.Boolean)")
    end)
    for i, key in ipairs(collect(keys, 4)) do
        local entry = { index = i - 1 }
        local enemy = getEnemy and safe(function() return getEnemy:call(nil, key, true) end)
        if enemy then
            local ctx = safe(function() return enemy:get_field("_Context") end)
            if ctx then
                local em = safe(function() return ctx:get_field("_Em") end)
                if em then
                    entry.em_type = safe_str(safe(function() return em:get_type_definition():get_full_name() end))
                    entry.em = sample_instance(em, 90)
                    -- direct guesses for an id getter on the Em/Layout
                    entry.em_enemyid = typecall1(entry.em_type or "app.cEnemy", "get_EnemyId", em, 0)
                end
            end
        end
        out.em_ids[#out.em_ids + 1] = entry
    end

    -- quest director: active em set / main target list
    local MM = safe(sdk.find_type_definition, "app.MissionManager")
    local mgr = MM and safe(function() return sdk.get_managed_singleton("app.MissionManager") end)
    local dir = mgr and typecall("app.MissionManager", "get_QuestDirector", mgr)
    if dir then
        local setId = typecall("app.cQuestDirector", "getActiveEmSet_EmIDs", dir)
        out.active_em_set_ids = {}
        for i, v in ipairs(collect(setId, 8)) do
            out.active_em_set_ids[#out.active_em_set_ids + 1] = { index = i - 1, value = safe_str(v) }
        end
        local mainList = typecall("app.cQuestDirector", "getActiveQuestMainTargetDataList", dir)
        out.main_target_list_count = #collect(mainList, 8)
    end

    -- cActiveQuestData target getters, with and without an index arg
    local aqd = mgr and typecall("app.MissionManager", "get_ActiveQuestData", mgr)
    if aqd then
        out.aqd_target_em_id_0 = typecall1("app.cActiveQuestData", "getTargetEmId", aqd, 0)
        out.aqd_target_role_id_0 = typecall1("app.cActiveQuestData", "getTargetEmRoleId", aqd, 0)
        out.aqd_target_legendary_id_0 = typecall1("app.cActiveQuestData", "getTargetEmLegendaryId", aqd, 0)
    end
end

local function sample_party(out)
    out.party = {}
    local PM = safe(sdk.find_type_definition, "app.PlayerManager")
    local pm = PM and safe(function() return sdk.get_managed_singleton("app.PlayerManager") end)
    if not pm then out.party_error = "no PlayerManager" return end
    local members = typecall("app.PlayerManager", "getQuestMembers", pm)
    local list = collect(members, 8)
    out.party_count = #list
    for i, m in ipairs(list) do
        local entry = { index = i - 1 }
        if m then
            entry.info_type = safe_str(safe(function() return m:get_type_definition():get_full_name() end))
            local ch = typecall("app.cPlayerManageInfo", "get_Character", m)
            if ch then
                entry.char_type = safe_str(safe(function() return ch:get_type_definition():get_full_name() end))
                entry.weapon_type = typecall("app.HunterCharacter", "get_WeaponType", ch)
                entry.weapon_id = typecall("app.HunterCharacter", "get_WeaponID", ch)
                entry.weapon_model_id = typecall("app.HunterCharacter", "get_WeaponModelID", ch)
                -- localized weapon-type name
                local WU = safe(sdk.find_type_definition, "app.WeaponUtil")
                local wtn = WU and safe(function()
                    return WU:get_method("getWeaponTypeName(app.WeaponDef.TYPE)")
                end)
                if wtn and entry.weapon_type ~= nil then
                    entry.weapon_type_name = localized(safe(function()
                        return wtn:call(nil, entry.weapon_type)
                    end))
                end
            end
        end
        out.party[#out.party + 1] = entry
    end
end

local function sample_runtime_deep()
    local out = { probe_version = PROBE_VERSION, deep = true }
    sample_quest_data(out)
    sample_boss_health(out)
    sample_em_ids(out)
    sample_party(out)
    sample_players(out) -- from v1: names/ids
    out.enum_weapon_type = enum_values("app.WeaponDef.TYPE")
    out.enum_enemy_id = enum_values("app.EnemyDef.ID")
    json.dump_file(OUT_RUNTIME, out)
    lastStatus = string.format("deep: quest=%s bosses=%d party=%d -> %s",
        tostring(out.quest and out.quest.target_em_id),
        #(out.boss_health or {}), #(out.party or {}), OUT_RUNTIME)
    log.info("[HuntDumperProbe] " .. lastStatus)
    return out
end

-- ---------------------------------------------------------------------------
-- Weapon-name probe (works in the hub; no hunt needed)
-- ---------------------------------------------------------------------------

local WEAPON_FIELDS = { "_WeaponLongSword", "_WeaponShortSword", "_WeaponTwinSword",
    "_WeaponTachi", "_WeaponHammer", "_WeaponWhistle", "_WeaponLance", "_WeaponGunLance",
    "_WeaponSlashAxe", "_WeaponChargeAxe", "_WeaponRod", "_WeaponBow",
    "_WeaponHeavyBowgun", "_WeaponLightBowgun" }

local function sample_weapon_data(v)
    if v == nil then return nil end
    local o = { type = safe_str(safe(function() return v:get_type_definition():get_full_name() end)) }
    o.name = localized(safe(function() return v:get_field("_Name") end))
    for _, fn in ipairs({ "_Name", "_Attack", "_Defence", "_Critical", "_WpAttr",
        "_AttrVal", "_Id", "_WeaponId", "_ModelId", "_Index", "_Rank", "_Rare" }) do
        local val = safe(function() return v:get_field(fn) end)
        if val ~= nil then o[fn] = safe_str(val) end
    end
    return o
end

local function probe_weapon()
    local out = { probe_version = PROBE_VERSION, weapon_probe = 2 }
    -- self hunter's live weapon ids
    local pm = safe(function() return sdk.get_managed_singleton("app.PlayerManager") end)
    local info = pm and typecall("app.PlayerManager", "getMasterPlayer", pm)
    local ch = info and typecall("app.cPlayerManageInfo", "get_Character", info)
    if ch then
        out.weapon_type = typecall("app.HunterCharacter", "get_WeaponType", ch)
        out.weapon_id = typecall("app.HunterCharacter", "get_WeaponID", ch)
        out.weapon_model_id = typecall("app.HunterCharacter", "get_WeaponModelID", ch)
    end

    -- per-type weapon data arrays (id -> name)
    local vdm = safe(function() return sdk.get_managed_singleton("app.VariousDataManager") end)
    local equipData = vdm and safe(function() return vdm._Setting._EquipDatas end)
    if equipData then
        out.weapon_arrays = {}
        for i, fname in ipairs(WEAPON_FIELDS) do
            local rec = { field = fname, type_idx = i - 1 }
            local arr = safe(function() return equipData[fname] end)
            if arr then
                rec.type = safe_str(safe(function() return arr:get_type_definition():get_full_name() end))
                local vals = safe(function() return arr:call("get_Values") end)
                    or safe(function() return arr._Values end)
                local list = collect(vals, 400)
                rec.count = #list
                rec.samples = {}
                rec.full = {}
                for j = 1, #list do
                    local idx = j - 1
                    local e = list[j]
                    rec.full[#rec.full + 1] = {
                        i = idx,
                        ix = safe_str(safe(function() return e:get_field("_Index") end)),
                        mid = safe_str(safe(function() return e:get_field("_ModelId") end)),
                        n = localized(safe(function() return e:get_field("_Name") end)),
                    }
                    if idx == out.weapon_id or idx == out.weapon_model_id or j <= 2 then
                        rec.samples[#rec.samples + 1] = { index = idx, data = sample_weapon_data(e) }
                    end
                end
            end
            out.weapon_arrays[#out.weapon_arrays + 1] = rec
            if (i - 1) == (out.weapon_type or -99) then out.self_type_array = rec end
        end
    end

    -- save equip chain (equipped weapon data)
    local sd = safe(function() return sdk.get_managed_singleton("app.SaveDataManager") end)
    local save = sd and typecall("app.SaveDataManager", "getCurrentUserSaveData", sd)
    if save then
        local equip = safe(function() return save:get_field("_Equip") end)
        out.equip_type = safe_str(safe(function() return equip and equip:get_type_definition():get_full_name() end))
        if equip then out.equip_sample = sample_instance(equip, 40) end
    end

    json.dump_file(OUT_RUNTIME, out)
    lastStatus = "weapon probe v2 -> " .. OUT_RUNTIME
    log.info("[HuntDumperProbe] " .. lastStatus)
    return out
end

-- ---------------------------------------------------------------------------
-- NPC-name probe (run mid-quest with support hunters present)
-- ---------------------------------------------------------------------------

local function probe_npc_names()
    local out = { probe_version = PROBE_VERSION, npc_probe = 1 }
    local nm = safe(function() return sdk.get_managed_singleton("app.NpcManager") end)
    out.npc_manager = nm ~= nil
    local catalog = nm and (safe(function() return nm:call("get_Catalog") end)
        or safe(function() return nm._Catalog end))
    out.catalog_type = safe_str(safe(function() return catalog and catalog:get_type_definition():get_full_name() end))
    out.setting_sample = sample_instance(nm and safe(function() return nm._Setting end), 30)

    local npm = nm and safe(function() return nm:call("get_PartnerManager") end)
    out.partner_manager = npm ~= nil
    local list = {}
    for _, meth in ipairs({ "getQuestMembers", "getManagedMembers", "getAdvisors" }) do
        for _, m in ipairs(collect(typecall("app.cNpcPartnerManager", meth, npm), 8)) do
            if m then list[#list + 1] = m end
        end
        if #list > 0 then out.member_source = meth break end
    end
    if #list == 0 and npm then
        for _, m in ipairs(collect(safe(function() return npm:get_field("_PartnerList") end), 8)) do
            if m then list[#list + 1] = m end
        end
        if #list > 0 then out.member_source = "_PartnerList" end
    end
    out.member_count = #list
    out.members = {}
    for _, m in ipairs(list) do
        local rec = {
            member_index = safe(function() return m:call("get_MemberIndex") end),
            npc_id = safe(function() return m:call("get_NpcID") end),
            porter_id = safe_str(safe(function() return m:call("get_PorterID") end)),
            otomo_id = safe_str(safe(function() return m:call("get_OtomoID") end)),
            partner_type = safe_str(safe(function() return m:call("get_PartnerType") end)),
            weapon = safe(function() return m:call("get_WeaponType") end),
            is_advisor = safe(function() return m:call("get_IsAdvisor") end),
            is_rescure = safe(function() return m:call("get_IsRescure") end),
            is_guest = safe(function() return m:call("get_IsGuest") end),
        }
        rec.createarg_sample = sample_instance(safe(function() return m._CreateArg end), 24)
        local pid = safe(function() return m:call("get_PorterID") end)
        if catalog and pid ~= nil then
            rec.partner_data_sample = sample_instance(safe(function() return catalog:call("getNpcPartnerData", pid) end), 24)
        end
        local npcid = rec.npc_id
        if npm and npcid ~= nil then
            rec.quest_member_sample = sample_instance(safe(function() return npm:call("getQuestMember", npcid) end), 24)
        end
        out.members[#out.members + 1] = rec
    end
    json.dump_file(OUT_NPC, out)
    lastStatus = "npc name probe -> " .. OUT_NPC
    log.info("[HuntDumperProbe] " .. lastStatus)
    return out
end

-- ---------------------------------------------------------------------------
-- Buff / abnormality probe (run mid-quest with active buffs)
-- ---------------------------------------------------------------------------

local function probe_buffs()
    local out = { probe_version = PROBE_VERSION, buff_probe = 1 }

    -- 1. managed types that might expose buff state
    local CANDIDATES = {
        "app.cStatusManager", "app.StatusManager",
        "app.cBuffManager", "app.BuffManager",
        "app.cAbnormalityManager", "app.AbnormalityManager",
        "app.cPlayerStatus", "app.PlayerStatus",
        "app.cHunterHealth", "app.HunterHealth",
        "app.cStatusBase", "app.StatusBase",
        "app.cConsumableManager", "app.ConsumableManager",
        "app.cSkillManager", "app.SkillManager",
        "app.cDebuffManager", "app.DebuffManager",
        "app.cSongManager", "app.SongManager",
    }
    out.managed_types = {}
    for _, tname in ipairs(CANDIDATES) do
        local td = safe(sdk.find_type_definition, tname)
        if td then
            local rec = { name = tname, exists = true }
            local fields = safe(function() return td:get_fields() end)
            if fields then
                rec.fields = {}
                for _, f in ipairs(fields) do
                    rec.fields[#rec.fields + 1] = {
                        name = safe(function() return f:get_name() end),
                        type = safe(function() return f:get_type():get_name() end),
                        static = safe(function() return f:is_static() end),
                    }
                end
            end
            local methods = safe(function() return td:get_methods() end)
            if methods then
                rec.methods = {}
                for _, m in ipairs(methods) do
                    rec.methods[#rec.methods + 1] = {
                        name = safe(function() return m:get_name() end),
                        full = safe(function() return m:get_full_name() end),
                        ret = safe(function() return m:get_return_type():get_name() end),
                    }
                end
            end
            out.managed_types[#out.managed_types + 1] = rec
        end
    end

    -- 2. local player via PlayerManager singleton
    local PM = safe(sdk.find_type_definition, "app.PlayerManager")
    local pm = PM and safe(function() return sdk.get_managed_singleton("app.PlayerManager") end)
    out.player_manager = pm ~= nil
    if not pm then
        out.error = "PlayerManager singleton not found"
        json.dump_file(OUT_BUFFS, out)
        lastStatus = "buff probe: no PlayerManager"
        return out
    end

    -- try common accessors for the local/master player
    local player = nil
    for _, mname in ipairs({ "getMasterPlayer", "get_LocalPlayer", "getSelfPlayer",
                             "getSelf", "getLocalPlayer", "getMasterPlayer()" }) do
        player = typecall("app.PlayerManager", mname, pm)
        if player then out.player_source = mname break end
    end
    if not player then
        -- try field access
        for _, fname in ipairs({ "_MasterPlayer", "_LocalPlayer", "_SelfPlayer",
                                 "<MasterPlayer>k__BackingField",
                                 "<LocalPlayer>k__BackingField" }) do
            player = safe(function() return pm:get_field(fname) end)
            if player then out.player_source = "field:" .. fname break end
        end
    end
    if not player then
        out.error = "local player not found via PlayerManager"
        json.dump_file(OUT_BUFFS, out)
        lastStatus = "buff probe: no local player"
        return out
    end

    -- deep-inspect the player object: all fields + buff-related methods
    out.player = sample_instance(player, 120)

    -- list every field name on the player (for hunting buff-related fields)
    local ptd = safe(function() return player:get_type_definition() end)
    if ptd then
        out.player_type = safe_str(safe(function() return ptd:get_full_name() end))
        out.player_fields = {}
        local fields = safe(function() return ptd:get_fields() end)
        if fields then
            for _, f in ipairs(fields) do
                local n = safe(function() return f:get_name() end) or ""
                local tn = safe(function() return f:get_type():get_name() end) or ""
                out.player_fields[#out.player_fields + 1] = { name = n, type = tn }
            end
        end
        -- also list all methods (for buff-related accessors)
        out.player_methods = {}
        local methods = safe(function() return ptd:get_methods() end)
        if methods then
            for _, m in ipairs(methods) do
                local n = safe(function() return m:get_name() end) or ""
                out.player_methods[#out.player_methods + 1] = {
                    name = n,
                    full = safe(function() return m:get_full_name() end),
                    ret = safe(function() return m:get_return_type():get_name() end),
                }
            end
        end
    end

    -- 3. follow <Character>k__BackingField -> HunterCharacter
    local ch = safe(function() return player:get_field("<Character>k__BackingField") end)
    if not ch then
        -- try method access
        for _, mname in ipairs({ "get_Character", "getHunterCharacter", "getCharacter" }) do
            ch = typecall("app.PlayerManager", mname, player)
            if ch then break end
        end
    end
    if ch then
        out.character_source = "field:<Character>k__BackingField"
        local ctd = safe(function() return ch:get_type_definition() end)
        out.character_type = safe_str(ctd and safe(function() return ctd:get_full_name() end))
        out.character = sample_instance(ch, 100)

        -- list ALL fields on HunterCharacter
        if ctd then
            out.character_fields = {}
            local cf = safe(function() return ctd:get_fields() end)
            if cf then
                for _, f in ipairs(cf) do
                    out.character_fields[#out.character_fields + 1] = {
                        name = safe(function() return f:get_name() end),
                        type = safe(function() return f:get_type():get_name() end),
                    }
                end
            end
            -- list ALL methods
            out.character_methods = {}
            local cm = safe(function() return ctd:get_methods() end)
            if cm then
                for _, m in ipairs(cm) do
                    out.character_methods[#out.character_methods + 1] = {
                        name = safe(function() return m:get_name() end),
                        full = safe(function() return m:get_full_name() end),
                        ret = safe(function() return m:get_return_type():get_name() end),
                    }
                end
            end
        end

        -- 5. follow buff-related sub-objects from cHunterStatus
        local st = typecall("app.HunterCharacter", "get_HunterStatus", ch)
        if st then
            -- read actual consumable timer values (via field get_data)
            local ib = safe(function() return st:get_field("_ItemBuff") end)
            if ib then
                out.itembuff_vals = {}
                for _, fname in ipairs({
                    "_Kairiki_Timer", "_Kairiki_G_Timer", "_KijinAmmo_Timer",
                    "_KijinPowder_Timer", "_Nintai_Timer", "_Nintai_G_Timer",
                    "_KoukaAmmo_Timer", "_KoukaPowder_Timer", "_DashJuice_Timer",
                    "_Immunizer_Timer", "_HotDrink_Timer", "_CoolerDrink_Timer",
                    "_PickUpStamina_Timer",
                }) do
                    out.itembuff_vals[fname] = field_value(ib, fname)
                end
                for _, ename in ipairs({ "_KijinDrink", "_KijinDrink_G",
                                         "_KoukaDrink", "_KoukaDrink_G" }) do
                    local obj = field_value(ib, ename)
                    if obj ~= nil then
                        out["enum" .. ename] = {
                            raw = safe_str(obj),
                            sample = sample_instance(obj, 12),
                        }
                    end
                end
                out.revival = field_value(ib, "_IsActiveRevivalDrink")
            end

            -- read actual debuff timer values
            local bc2 = safe(function() return st:get_field("_BadConditions") end)
            if bc2 then
                out.badcond_vals = {}
                for _, fname in ipairs({
                    "_Poison", "_Fire", "_Stun", "_Paralyze", "_Sleep",
                    "_Blast", "_Bleed", "_Frenzy", "_Sticky", "_Frozen",
                    "_DefDown", "_Stench", "_Elec", "_Water", "_Ice", "_Dragon",
                }) do
                    local obj = safe(function() return bc2:get_field(fname) end)
                    if obj then
                        local rec = {}
                        for _, tf in ipairs({ "_DurationTimer", "_DurationTime",
                                              "_DamageIntervalTimer", "_StunAccumulateRate",
                                              "_ReduceTimer", "_CureTimer",
                                              "_CureAccumerator", "_State" }) do
                            local v = field_value(obj, tf)
                            if v ~= nil then rec[tf] = v end
                        end
                        out.badcond_vals[fname] = rec
                    end
                end
                out.badcond_any_active = field_value(bc2, "_IsAnyCondActive")
            end

            -- read meal effect timer
            local me = safe(function() return st:get_field("_MealEffect") end)
            if me then
                out.meal_duration = field_value(me, "_DurationTimer")
                out.meal_max = field_value(me, "_TimerMax")
                out.meal_active = field_value(me, "_IsTimerActive")
                out.meal_effect_active = field_value(me, "_IsEffectActive")
            end
            local SUB_OBJECTS = {
                { field = "_ItemBuff",     label = "itembuff" },
                { field = "_Skill",        label = "skillsub" },
                { field = "_MealEffect",   label = "mealeffect" },
                { field = "_BadConditions", label = "badconditions" },
            }
            for _, sub in ipairs(SUB_OBJECTS) do
                local obj = safe(function() return st:get_field(sub.field) end)
                if obj then
                    local otd = safe(function() return obj:get_type_definition() end)
                    out[sub.label .. "_type"] = safe_str(otd and safe(function() return otd:get_full_name() end))
                    out[sub.label] = sample_instance(obj, 80)
                    if otd then
                        out[sub.label .. "_fields"] = {}
                        local of = safe(function() return otd:get_fields() end)
                        if of then
                            for _, f in ipairs(of) do
                                out[sub.label .. "_fields"][#out[sub.label .. "_fields"] + 1] = {
                                    name = safe(function() return f:get_name() end),
                                    type = safe(function() return f:get_type():get_name() end),
                                }
                            end
                        end
                        out[sub.label .. "_getters"] = {}
                        local om = safe(function() return otd:get_methods() end)
                        if om then
                            for _, m in ipairs(om) do
                                local fname = safe(function() return m:get_full_name() end) or ""
                                if fname:find("get_") and fname:find("%(%)$") then
                                    local v = safe(function() return m:call(obj) end)
                                    out[sub.label .. "_getters"][#out[sub.label .. "_getters"] + 1] = {
                                        name = fname, value = safe_str(v),
                                    }
                                end
                            end
                        end
                    end
                end
            end

            -- also follow cHunterSkill sub-objects (HH songs, palico, skill dict)
            local sk = safe(function() return st:get_field("_Skill") end)
            if sk then
                local SKILL_SUBS = {
                    { field = "_CurrentSkillInfoDic", label = "skillinfo" },
                    { field = "_NextSkillInfo",       label = "nextskill" },
                    { field = "_OtomoMusicSkillTimer", label = "otomoskill" },
                    { field = "_Wp05MusicSkill",      label = "wp05music" },
                }
                for _, sub in ipairs(SKILL_SUBS) do
                    local obj = safe(function() return sk:get_field(sub.field) end)
                    if obj then
                        local otd = safe(function() return obj:get_type_definition() end)
                        out[sub.label .. "_type"] = safe_str(otd and safe(function() return otd:get_full_name() end))
                        out[sub.label] = sample_instance(obj, 80)
                        if otd then
                            out[sub.label .. "_fields"] = {}
                            local of = safe(function() return otd:get_fields() end)
                            if of then
                                for _, f in ipairs(of) do
                                    out[sub.label .. "_fields"][#out[sub.label .. "_fields"] + 1] = {
                                        name = safe(function() return f:get_name() end),
                                        type = safe(function() return f:get_type():get_name() end),
                                    }
                                end
                            end
                            out[sub.label .. "_getters"] = {}
                            local om = safe(function() return otd:get_methods() end)
                            if om then
                                for _, m in ipairs(om) do
                                    local fname = safe(function() return m:get_full_name() end) or ""
                                    if fname:find("get_") and fname:find("%(%)$") then
                                        local v = safe(function() return m:call(obj) end)
                                        out[sub.label .. "_getters"][#out[sub.label .. "_getters"] + 1] = {
                                            name = fname, value = safe_str(v),
                                        }
                                    end
                                end
                            end
                        end
                    end
                end

                -- dump array contents: HH song timers, palico timers, skill info
                local function dump_array(label, arr)
                    if arr == nil then return end
                    local otd = safe(function() return arr:get_type_definition() end)
                    out[label .. "_arrtype"] = safe_str(otd and safe(function() return otd:get_full_name() end))
                    out[label .. "_arrlen"] = safe(function() return #arr end)
                    -- read up to 40 elements
                    local vals = {}
                    for i = 0, 39 do
                        local v = safe(function() return arr[i] end)
                        if v == nil then break end
                        vals[#vals + 1] = safe_str(v)
                    end
                    out[label .. "_arr"] = vals
                end
                -- boxed Single[] -> numbers (HH songs, palico songs)
                local function read_float_array(arr, maxi)
                    if arr == nil then return nil end
                    local vals = {}
                    for i = 0, (maxi or 58) do
                        local elem = safe(function() return arr[i] end)
                        if elem == nil then break end
                        vals[#vals + 1] = boxed_float(elem)
                    end
                    return vals
                end
                -- HH song timers
                local wp05 = safe(function() return sk:get_field("_Wp05MusicSkill") end)
                if wp05 then
                    out.wp05_skilltimer_vals = read_float_array(safe(function() return wp05:get_field("_SkillTimer") end))
                    out.wp05_skillmaxtimer_vals = read_float_array(safe(function() return wp05:get_field("_SkillMaxTimer") end))
                    out.wp05_skilloverlap_vals = read_float_array(safe(function() return wp05:get_field("_SkillOverlap") end))
                    out.wp05_healthregen = field_value(wp05, "_CurrentHealthRegeneTime")
                    out.wp05_staminaregen = field_value(wp05, "_CurrentStaminaRegeneTime")
                end
                -- palico song timers
                local otomo = safe(function() return sk:get_field("_OtomoMusicSkillTimer") end)
                out.otomo_timer_vals = read_float_array(otomo, 40)
                -- skill info array: read _Skill and _SkillLv from first non-null
                local skillarr = safe(function() return sk:get_field("_CurrentSkillInfoDic") end)
                if skillarr then
                    local otd = safe(function() return skillarr:get_type_definition() end)
                    out.skillinfo_arrtype = safe_str(otd and safe(function() return otd:get_full_name() end))
                    out.skillinfo_arrlen = safe(function() return #skillarr end)
                    out.skillinfo_active = {}
                    for i = 0, 30 do
                        local elem = safe(function() return skillarr[i] end)
                        if elem == nil then break end
                        local sid = field_value(elem, "_Skill")
                        local slv = field_value(elem, "_SkillLv")
                        local sdata = field_value(elem, "_SkillData")
                        if sid ~= nil or slv ~= nil then
                            out.skillinfo_active[#out.skillinfo_active + 1] = {
                                index = i,
                                skill = sid,
                                level = safe_str(slv),
                                has_data = sdata ~= nil,
                            }
                        end
                    end
                end
            end

            -- follow representative debuff sub-objects to see their timer fields
            local DEBUFF_REPS = {
                { field = "_Poison", label = "dpoison" },
                { field = "_Fire",   label = "dfire" },
                { field = "_Stun",   label = "dstun" },
                { field = "_Paralyze", label = "dparalyze" },
                { field = "_Sleep",  label = "dsleep" },
                { field = "_Blast",  label = "dblast" },
                { field = "_Bleed",  label = "dbleed" },
                { field = "_Frenzy", label = "dfrenzy" },
            }
            local bc = safe(function() return st:get_field("_BadConditions") end)
            if bc then
                for _, sub in ipairs(DEBUFF_REPS) do
                    local obj = safe(function() return bc:get_field(sub.field) end)
                    if obj then
                        local otd = safe(function() return obj:get_type_definition() end)
                        out[sub.label .. "_type"] = safe_str(otd and safe(function() return otd:get_full_name() end))
                        if otd then
                            out[sub.label .. "_fields"] = {}
                            local of = safe(function() return otd:get_fields() end)
                            if of then
                                for _, f in ipairs(of) do
                                    out[sub.label .. "_fields"][#out[sub.label .. "_fields"] + 1] = {
                                        name = safe(function() return f:get_name() end),
                                        type = safe(function() return f:get_type():get_name() end),
                                    }
                                end
                            end
                            out[sub.label .. "_getters"] = {}
                            local om = safe(function() return otd:get_methods() end)
                            if om then
                                for _, m in ipairs(om) do
                                    local fname = safe(function() return m:get_full_name() end) or ""
                                    if fname:find("get_") and fname:find("%(%)$") then
                                        local v = safe(function() return m:call(obj) end)
                                        out[sub.label .. "_getters"][#out[sub.label .. "_getters"] + 1] = {
                                            name = fname, value = safe_str(v),
                                        }
                                    end
                                end
                            end
                        end
                    end
                end
            end
        end
        local ACCESSORS = {
            { getter = "get_HunterStatus", label = "status" },
            { getter = "get_HunterHealth", label = "health" },
            { getter = "get_HunterSkill",  label = "skill" },
            { getter = "get_HunterStamina", label = "stamina" },
        }
        for _, acc in ipairs(ACCESSORS) do
            local obj = typecall("app.HunterCharacter", acc.getter, ch)
            if obj then
                local label = acc.label
                local otd = safe(function() return obj:get_type_definition() end)
                out[label .. "_source"] = acc.getter
                out[label .. "_type"] = safe_str(otd and safe(function() return otd:get_full_name() end))
                out[label] = sample_instance(obj, 120)
                -- list ALL fields
                if otd then
                    out[label .. "_fields"] = {}
                    local of = safe(function() return otd:get_fields() end)
                    if of then
                        for _, f in ipairs(of) do
                            out[label .. "_fields"][#out[label .. "_fields"] + 1] = {
                                name = safe(function() return f:get_name() end),
                                type = safe(function() return f:get_type():get_name() end),
                            }
                        end
                    end
                    -- call every 0-arg getter
                    out[label .. "_getters"] = {}
                    local om = safe(function() return otd:get_methods() end)
                    if om then
                        for _, m in ipairs(om) do
                            local fname = safe(function() return m:get_full_name() end) or ""
                            if fname:find("get_") and fname:find("%(%)$") then
                                local v = safe(function() return m:call(obj) end)
                                out[label .. "_getters"][#out[label .. "_getters"] + 1] = {
                                    name = fname, value = safe_str(v),
                                }
                            end
                        end
                    end
                end
            end
        end
    end

    json.dump_file(OUT_BUFFS, out)
    lastStatus = string.format("buff probe: char=%s status=%s skill=%s -> %s",
        out.character_type or "?", out.status_type or "?", out.skill_type or "?", OUT_BUFFS)
    log.info("[HuntDumperProbe] " .. lastStatus)
    return out
end

-- ---------------------------------------------------------------------------
-- UI
-- ---------------------------------------------------------------------------

re.on_draw_ui(function()
    if imgui.tree_node("HuntDumper Probe (R0)") then
        imgui.text("v" .. tostring(PROBE_VERSION))
        imgui.text("Writes JSON to reframework/data/")
        imgui.separator()

        if imgui.button("Dump types") then
            local ok, err = pcall(dump_types)
            if not ok then lastStatus = "dump_types error: " .. tostring(err) end
        end
        imgui.same_line()
        if imgui.button("Sample runtime") then
            local ok, err = pcall(sample_runtime)
            if not ok then lastStatus = "sample_runtime error: " .. tostring(err) end
        end
        imgui.same_line()
        if imgui.button("Deep sample (v2)") then
            local ok, err = pcall(sample_runtime_deep)
            if not ok then lastStatus = "deep error: " .. tostring(err) end
        end
        imgui.same_line()
        if imgui.button("Probe weapon") then
            local ok, err = pcall(probe_weapon)
            if not ok then lastStatus = "weapon probe error: " .. tostring(err) end
        end
        imgui.same_line()
        if imgui.button("Probe NPCs") then
            local ok, err = pcall(probe_npc_names)
            if not ok then lastStatus = "npc probe error: " .. tostring(err) end
        end
        imgui.same_line()
        if imgui.button("Probe buffs") then
            local ok, err = pcall(probe_buffs)
            if not ok then lastStatus = "buff probe error: " .. tostring(err) end
        end
        imgui.same_line()
        if imgui.button("Dump types + sample") then
            local ok, err = pcall(function()
                dump_types()
                sample_runtime()
            end)
            if not ok then lastStatus = "combined error: " .. tostring(err) end
        end

        imgui.separator()
        imgui.text("status: " .. tostring(lastStatus))
        imgui.text("Tip: sample mid-quest with monsters alive and a few hits landed.")
        imgui.tree_pop()
    end
end)

log.info("[HuntDumperProbe] loaded (v" .. tostring(PROBE_VERSION) .. ")")
