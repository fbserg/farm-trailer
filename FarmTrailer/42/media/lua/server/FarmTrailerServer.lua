if isClient() then return end
local F = require "FarmTrailer"

local function addObject(square, sprite, name)
    local object = IsoObject.new(square, sprite, name)
    square:AddTileObject(object)
    return object
end

local originalWalls = {
    ["walls_exterior_wooden_01_41"] = {name = "Farm wall", kind = "north"},
    ["walls_exterior_wooden_01_40"] = {name = "Farm wall", kind = "west"},
    ["fencing_01_25"] = {name = "Farm fence", kind = "north"},
    ["fencing_01_24"] = {name = "Farm fence", kind = "west"},
}

function F.upgradeBoundary(square)
    local room, mode = F.boundaryAt(square:getX(), square:getY(), square:getZ())
    if not room then return end
    local objects, changes = square:getObjects(), {}
    local floor, protected = square:getFloor(), false
    local dx, dy = square:getX() - room.x, square:getY() - room.y
    for i = 0, objects:size() - 1 do
        local object = objects:get(i)
        if F.isBoundary(object) then
            protected = true
        elseif object ~= floor then
            local sprite = object:getSprite()
            local old = sprite and originalWalls[sprite:getName()]
            local correctEdge = old and ((old.kind == "north" and (dy == 0 or dy == 41))
                or (old.kind == "west" and (dx == 0 or dx == 13)))
            if mode == "wall" and old and object:getName() == old.name and correctEdge then
                changes[#changes + 1] = {object = object, kind = old.kind}
            else
                if not square:getModData().FarmTrailerBoundaryConflict then
                    print("[FarmTrailer] Boundary upgrade skipped player/map construction at "
                        .. square:getX() .. "," .. square:getY())
                    square:getModData().FarmTrailerBoundaryConflict = true
                end
                return -- Preflight the whole square before touching an original wall.
            end
        end
    end
    if square:getRoom() then return end
    for _, change in ipairs(changes) do
        local object = change.object
        object:setSpriteFromName(F.boundarySprites[change.kind].name)
        object:getModData().FarmTrailerBoundary = true
        object:transmitModData()
        object:transmitUpdatedSpriteToClients()
    end
    if mode == "outer" and not protected then
        local object = addObject(square, F.boundarySprites.outer.name, "Farm boundary")
        object:getModData().FarmTrailerBoundary = true
        object:transmitCompleteItemToClients()
    end
    if #changes > 0 or (mode == "outer" and not protected) then
        square:getModData().FarmTrailerBoundaryConflict = nil
        square:RecalcAllWithNeighbours(true)
        square:transmitModdata()
    end
end

function F.buildSquare(square)
    local room = F.roomAt(square:getX(), square:getY(), square:getZ())
    if not room or square:getModData().FarmTrailerBuilt then
        F.upgradeBoundary(square)
        return
    end
    assert(not square:getRoom(), "Farm Trailer needs an unoccupied outdoor map band")
    assert(square:getObjects():size() <= 1, "Farm Trailer found existing construction in its reserved band")
    local dx, dy = square:getX() - room.x, square:getY() - room.y
    square:addFloor("blends_natural_01_16")
    if dy == 0 or dy == 41 then
        addObject(square, "walls_exterior_wooden_01_41", "Farm wall"):transmitCompleteItemToClients()
    end
    if dx == 0 or dx == 13 then
        addObject(square, "walls_exterior_wooden_01_40", "Farm wall"):transmitCompleteItemToClients()
    end
    if dy == 2 and (dx == 2 or dx == 3) then
        local object = addObject(square, "carpentry_02_54", "Farm water collector")
        local script = getScriptManager():getGameEntityScript("Base.RainCollector")
        GameEntityFactory.CreateIsoObjectEntity(object, script, true)
        object:getModData().FarmTrailerWater = F.key(room)
        object:transmitCompleteItemToClients()
        assert(object:getFluidContainer():getCapacity() == 400, "Unexpected native collector capacity")
    end
    square:getModData().FarmTrailerBuilt = true
    F.upgradeBoundary(square)
    square:RecalcAllWithNeighbours(true)
    square:transmitModdata()
end
Events.LoadGridsquare.Add(F.buildSquare)

function F.waterObjects(room)
    local objects = {}
    for dx = 2, 3 do
        local sq = getCell():getGridSquare(room.x + dx, room.y + 2, room.z)
        if not sq then return nil end -- Normal unloaded chunk, use the last snapshot.
        local list = sq:getObjects()
        for i = 0, list:size() - 1 do
            local object = list:get(i)
            if object:getModData().FarmTrailerWater == F.key(room) then
                objects[#objects + 1] = object
            end
        end
    end
    return objects
end

function F.updateWater(room)
    local state = F.state(room)
    local objects = F.waterObjects(room)
    if not objects then return end
    state.observed = true
    state.known, state.capacity = 0, 0
    for _, object in ipairs(objects) do
        local free = object:getFluidCapacity() - object:getFluidAmount()
        local amount = math.min(free, state.pending)
        -- Consume the pending delivery before any re-entrant fluid events.
        state.pending = state.pending - amount
        if amount > 0 then
            object:addFluid(FluidType.TaintedWater, amount)
            object:sync()
        end
        state.known = state.known + object:getFluidAmount()
        state.capacity = state.capacity + object:getFluidCapacity()
    end
    -- Rain may have filled the collectors since the last exterior snapshot.
    state.pending = math.min(state.pending, state.capacity - state.known)
end

function F.canPump(player, vehicle)
    return F.pumpReady(player, vehicle) and F.vehicleRoom(vehicle) ~= nil
end

function F.pump(player, vehicle)
    if not F.canPump(player, vehicle) then return 0 end
    local room = F.vehicleRoom(vehicle)
    F.updateWater(room)
    local state = F.state(room)
    local amount = math.min(20, state.capacity - state.known - state.pending)
    if amount <= 0 then return 0 end
    local part, owner = F.power(vehicle)
    local battery = part:getInventoryItem()
    battery:setCurrentUsesFloat(battery:getCurrentUsesFloat() - amount * 0.00025)
    owner:transmitPartUsedDelta(part)
    state.pending = state.pending + amount
    F.updateWater(room)
    F.updateMass(vehicle, room)
    return amount
end

function F.updateMass(vehicle, room)
    local state = F.state(room)
    local part = assert(vehicle:getPartById("TrailerAnimalFood"), "Missing livestock trailer part")
    local data = part:getModData()
    data.FarmTrailerDryMass = data.FarmTrailerDryMass or vehicle:getInitialMass()
    data.FarmTrailerWaterMass = state.known + state.pending
    data.FarmTrailerWaterObserved = state.observed == true
    vehicle:transmitPartModData(part)
    F.applyMass(vehicle, data)
end

function F.track(vehicle)
    if not F.isFarmVehicle(vehicle) then return end
    local id = vehicle:getModData().projectRV_uniqueId
    local room = F.vehicleRoom(vehicle)
    if not id or not room then return end
    local data = F.rvData()
    data.Vehicles = data.Vehicles or {}
    data.Vehicles[tostring(id)] = {x = vehicle:getX(), y = vehicle:getY(), z = vehicle:getZ()}
    F.updateMass(vehicle, room)
end

function F.cleanOutsideZombies(room)
    for x = room.x - 5, room.x + 18 do
        for y = room.y - 5, room.y + 46 do
            if not F.contains(room, x, y, room.z) then
                local square = getCell():getGridSquare(x, y, room.z)
                local moving = square and square:getMovingObjects()
                if moving then
                    for i = moving:size() - 1, 0, -1 do
                        local object = moving:get(i)
                        if instanceof(object, "IsoZombie") then
                            object:removeFromSquare()
                            object:removeFromWorld()
                        end
                    end
                end
            end
        end
    end
end

function F.exit(player)
    local record = F.playerData(player)
    if not F.isFarmRecord(record) then return false end
    local room = record.ActualRoom
    if not room or player:getZ() ~= room.z or player:getX() < room.x - 10
        or player:getX() >= room.x + 24 or player:getY() < room.y - 10
        or player:getY() >= room.y + 52 then return false end
    local vehicles = getCell():getVehicles():iterator()
    while vehicles:hasNext() do
        local vehicle = vehicles:next()
        if tostring(vehicle:getModData().projectRV_uniqueId) == record.VehicleId then F.track(vehicle) end
    end
    local position = assert(F.rvData().Vehicles[record.VehicleId], "Missing farm trailer return position")
    F.updateWater(room)
    F.cleanOutsideZombies(room)
    -- No corpse, animal, crop, or furniture cleanup on this exit path.
    F.rvData().Players[player:getModData().projectRV_playerId] = nil
    if isServer() then
        sendServerCommand(player, "RVClient", "teleportToVehicle", {
            x = position.x, y = position.y, z = position.z, seat = -1,
        })
    else
        player:setSitOnGround(false)
        player:setSittingOnFurniture(false)
        player:setX(position.x); player:setLastX(position.x)
        player:setY(position.y); player:setLastY(position.y)
        player:setZ(position.z); player:setLastZ(position.z)
    end
    return true
end

function F.installServerHooks()
    if not isMultiplayer() then return end
    local originalEntry = GetInToRV
    GetInToRV = function(player, vehicle)
        return F.withVehicleType(vehicle, originalEntry, player, vehicle)
    end
    local originalExit = RVServer.GetOutFromRV
    RVServer.GetOutFromRV = function(player)
        local record = F.playerData(player)
        if F.isFarmRecord(record) then F.exit(player); return end
        return originalExit(player)
    end
end
Events.OnInitWorld.Add(F.installServerHooks)

-- Native AnimalInventoryItem saves the entire animal during a portal handoff.
function F.releaseCargo(player)
    local item = player:getPrimaryHandItem()
    if not item or not instanceof(item, "AnimalInventoryItem") then return end
    local target = item:getModData().FarmTrailerTransfer
    if not target then return end
    local square = player:getSquare()
    if not square then return end
    local room = F.roomAt(square:getX(), square:getY(), square:getZ())
    if (target == "farm") ~= (room ~= nil) then return end
    if room then
        local record = F.playerData(player)
        local expected = item:getModData().FarmTrailerTransferVehicle
        if not expected or not F.isFarmRecord(record) or tostring(record.VehicleId) ~= expected
            or not record.ActualRoom or F.key(record.ActualRoom) ~= F.key(room) then return end
        if not square:getModData().FarmTrailerBuilt then return end
    elseif F.isFarmRecord(F.playerData(player)) then
        return -- A failed exit must not release an animal just beyond the farm wall.
    end
    -- This native drop path restores the animal state and identity, and handles networking.
    assert(square:AddWorldInventoryItem(item, 0.5, 0.5, 0, true), "Native animal release failed")
    player:getInventory():Remove(item)
    player:setPrimaryHandItem(nil)
    player:setSecondaryHandItem(nil)
    sendRemoveItemFromContainer(player:getInventory(), item)
end

function F.awaitCargo(player)
    local ticks = 0
    local function releaseWhenReady()
        ticks = ticks + 1
        F.releaseCargo(player)
        local item = player:getPrimaryHandItem()
        if ticks >= 600 or not item or not item:getModData().FarmTrailerTransfer then
            Events.OnTick.Remove(releaseWhenReady)
        end
    end
    Events.OnTick.Add(releaseWhenReady)
end

local function maintain()
    local assigned = F.rvData()["AssignedRooms" .. F.type] or {}
    for _, room in pairs(assigned) do F.updateWater(room) end
    local vehicles = getCell():getVehicles():iterator()
    while vehicles:hasNext() do F.track(vehicles:next()) end
    if isServer() then
        local players = getOnlinePlayers()
        for i = 0, players:size() - 1 do F.releaseCargo(players:get(i)) end
    else
        for i = 0, getNumActivePlayers() - 1 do
            local player = getSpecificPlayer(i)
            if player then F.releaseCargo(player) end
        end
    end
end
Events.EveryOneMinute.Add(maintain)
-- An entry can precede collector chunk loads. A newer entry cancels the old wait.
local waterEntries = {}
function F.awaitWaterNotice(context)
    local player, room = context.player, context.room
    if not player or not room then return end
    local record = F.playerData(player)
    if not record then return end
    local token, ticks = {}, 0
    local checkWater
    waterEntries[player] = token
    local function finish()
        Events.OnTick.Remove(checkWater)
        if waterEntries[player] == token then waterEntries[player] = nil end
    end
    -- ceiling: 600 ticks per entry, revisit only if native chunk loading needs longer.
    checkWater = function()
        ticks = ticks + 1
        if waterEntries[player] ~= token or F.playerData(player) ~= record then finish(); return end
        if not F.waterObjects(room) then
            if ticks >= 600 then finish() end
            return
        end
        finish()
        F.updateWater(room)
        F.updateMass(context.vehicle, room)
        local amount = F.state(room).known + F.state(room).pending
        if amount >= F.capacity * 0.2 then return end
        if isServer() then
            sendServerCommand(player, "FarmTrailer", "waterLow", {onlineID = player:getOnlineID(), amount = amount})
        else
            HaloTextHelper.addBadText(player, "Farm water low: " .. math.floor(amount) .. " / " .. F.capacity .. " L")
        end
    end
    Events.OnTick.Add(checkWater)
end
return F
