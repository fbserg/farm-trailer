-- Farm Trailer uses Project RV Interior's documented vehicle registration table.
FarmTrailer = FarmTrailer or {}
local F = FarmTrailer
F.type = "FarmTrailer12x40"
F.script = "Base.TrailerKI5livestock"
F.width, F.height = 12, 40
F.capacity = 800
F.rooms = {}
-- ceiling: 38 farms, add a separately mapped pool before increasing this band.
for col = 0, 37 do
    F.rooms[#F.rooms + 1] = {x = 22560 + col * 60, y = 12500, z = 0}
end

function F.key(room) return room.x .. ":" .. room.y end

function F.contains(room, x, y, z)
    return z == room.z and x >= room.x and x < room.x + 14
        and y >= room.y and y < room.y + 42
end

function F.roomAt(x, y, z)
    if z ~= 0 or y < 12500 or y >= 12542 then return nil end
    local col = math.floor((x - 22560) / 60)
    local room = F.rooms[col + 1]
    if room and F.contains(room, x, y, z) then return room end
end

function F.isVehicle(vehicle)
    return vehicle and vehicle:getScript():getFullName() == F.script
end

function F.isFarmVehicle(vehicle)
    if not F.isVehicle(vehicle) then return false end
    local kind = vehicle:getModData().projectRV_type
    return kind == nil or kind == F.type
end

function F.isFarmRecord(record)
    if not record then return false end
    if record.RoomType == F.type then return true end
    -- The first release could save a farm occupant with the trailer's old type.
    local room = record.ActualRoom
    local farm = room and F.roomAt(room.x, room.y, room.z)
    return farm ~= nil and farm.x == room.x and farm.y == room.y
end

function F.withVehicleType(vehicle, callback, ...)
    if not F.isVehicle(vehicle) then return callback(...) end
    local kind = vehicle:getModData().projectRV_type or F.type
    local types = require("RVVehicleTypes").VehicleTypes
    local saved = assert(types[kind], "Saved trailer interior type is unavailable")
    -- The parent resolves scripts before persisted types. Route this synchronous
    -- call to the saved type, without migrating either assignment or its contents.
    local originals = {}
    for _, def in pairs(types) do
        originals[def] = def.scripts
        local scripts = {}
        for _, script in ipairs(def.scripts) do
            if script ~= F.script then scripts[#scripts + 1] = script end
        end
        if def == saved then scripts[#scripts + 1] = F.script end
        def.scripts = scripts
    end
    local ok, result = pcall(callback, ...)
    for def, scripts in pairs(originals) do def.scripts = scripts end
    if not ok then error(result) end
    return result
end

-- This hook runs after successful parent entry but before its free utilities.
require("RVHooks").register("postEnter", function(context)
    if context.typeKey == F.type then
        if context.side ~= "client" then F.awaitWaterNotice(context) end
        return false
    end
end)

function F.rvData() return ModData.getOrCreate("modPROJECTRVInterior") end

function F.playerData(player)
    local id = player:getModData().projectRV_playerId
    local data = F.rvData()
    return id and data.Players and data.Players[id]
end

function F.state(room)
    local data = ModData.getOrCreate("FarmTrailer")
    local key = F.key(room)
    if not data[key] then data[key] = {pending = 0, known = 0, capacity = F.capacity} end
    return data[key]
end

function F.vehicleRoom(vehicle)
    local id = vehicle:getModData().projectRV_uniqueId
    local assigned = F.rvData()["AssignedRooms" .. F.type]
    return id and assigned and assigned[tostring(id)]
end

function F.findWater(vehicle)
    local vx, vy = math.floor(vehicle:getX()), math.floor(vehicle:getY())
    -- ceiling: a six-tile intake hose, change the hose model before extending it.
    for x = vx - 6, vx + 6 do
        for y = vy - 6, vy + 6 do
            local sq = getCell():getGridSquare(x, y, vehicle:getZ())
            if sq and sq:getProperties():has(IsoFlagType.water) then return sq end
        end
    end
end

function F.power(vehicle)
    local part = vehicle:getPartById("Battery")
    local partner = vehicle:getTowingPartner()
    if not part and partner then part = partner:getPartById("Battery") end
    if part and part:getInventoryItem() then return part, part:getVehicle() end
end

function F.pumpReady(player, vehicle)
    if not F.isFarmVehicle(vehicle) or math.abs(vehicle:getCurrentSpeedKmHour()) > 0.1 then return false end
    if player:getZ() ~= vehicle:getZ() or player:DistToSquared(vehicle) > 25 then return false end
    if not player:getInventory():containsTypeRecurse("RubberHose") then return false end
    if not F.findWater(vehicle) then return false end
    local part = F.power(vehicle)
    if not part or part:getInventoryItem():getCurrentUsesFloat() < 0.005 then return false end
    return true
end

function F.applyMass(vehicle, data)
    vehicle:setInitialMass(data.FarmTrailerDryMass + data.FarmTrailerWaterMass)
    vehicle:updateTotalMass()
end

function F.register()
    local types = require("RVVehicleTypes").VehicleTypes
    -- Refuse to put this pool over another add-on's room.
    for _, def in pairs(types) do
        if def ~= types[F.type] then
            for _, other in ipairs(def.rooms) do
                for _, room in ipairs(F.rooms) do
                    assert(other.z ~= room.z or other.x + def.roomWidth < room.x - 1
                        or other.x > room.x + 14 or other.y + def.roomHeight < room.y - 1
                        or other.y > room.y + 42, "Farm Trailer pool overlaps an RV room")
                end
            end
        end
    end
    -- Validate the entire pool before changing any parent's vehicle registration.
    for _, def in pairs(types) do
        if def ~= types[F.type] then
            for i = #def.scripts, 1, -1 do
                if def.scripts[i] == F.script then table.remove(def.scripts, i) end
            end
        end
    end
    types[F.type] = {
        scripts = {F.script}, rooms = F.rooms, offset = {x = 6, y = 3},
        requiresSeat = false, requiresTrunk = true,
        trunkParts = {AnimalEntry = true, TrailerAnimalFood = true},
        genX = 0, genY = 0, genFloor = 1, roomWidth = F.width + 1, roomHeight = F.height + 1,
    }
end
Events.OnInitWorld.Add(F.register)
require "FarmTrailerBoundary"
function F.waterStatusText(vehicle)
    local data = vehicle:getPartById("TrailerAnimalFood"):getModData()
    if not data.FarmTrailerWaterObserved then return "Farm water: enter farm to check" end
    local amount = data.FarmTrailerWaterMass
    local text = "Farm water: " .. math.floor(amount) .. " / " .. F.capacity .. " L"
    if amount < F.capacity * 0.2 then text = text .. " (LOW)" end
    return text .. " (snapshot)"
end

return F
