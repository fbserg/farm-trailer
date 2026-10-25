local F = require "FarmTrailer"
require "TimedActions/ISFarmTrailerAction"
F.entryMenus = {}

function F.enterFromMenu(player)
    local command = assert(F.entryMenus[player:getPlayerNum()], "Open the trailer radial menu before transfer")
    command[1](command[2], command[3], command[4], command[5], command[6], command[7])
end

function F.requestExit(player)
    if isClient() then sendClientCommand(player, "RVServer", "exitRV", {}) else F.exit(player) end
end

local function queuePump(player, vehicle)
    for _ = 1, 40 do
        ISTimedActionQueue.add(ISFarmTrailerAction:new(player, "pump", vehicle))
    end
end

local function install()
    local originalMenu = ISVehicleMenu.showRadialMenu
    ISVehicleMenu.showRadialMenu = function(player, ...)
        F.entryMenus[player:getPlayerNum()] = nil
        originalMenu(player, ...)
        local vehicle = ISVehicleMenu.getVehicleToInteractWith(player)
        if not F.isVehicle(vehicle) then return end
        local menu = getPlayerRadialMenu(player:getPlayerNum())
        for _, slice in ipairs(menu.slices) do
            if slice.text == getText("ContextMenu_GetInToRV") then
                F.entryMenus[player:getPlayerNum()] = slice.command
                break
            end
        end
        if F.pumpReady(player, vehicle) then
            menu:addSlice("Fill farm tanks", getTexture("Item_WaterBottleFull"), queuePump, player, vehicle)
        end
        local animals = vehicle:getAnimals()
        if not F.entryMenus[player:getPlayerNum()] then return end
        if animals:size() > 0 then
            menu:addSlice("Bring livestock into farm", getTexture("media/ui/AnimalActions_Grab.png"), function()
                local choices = ISContextMenu.get(player:getPlayerNum(), getMouseX(), getMouseY())
                for i = 0, animals:size() - 1 do
                    local animal = animals:get(i)
                    choices:addOption(animal:getFullName(), player, function()
                        ISTimedActionQueue.add(ISFarmTrailerAction:new(player, "animalIn", vehicle, animal))
                    end)
                end
            end)
        end
    end
    if not isMultiplayer() then
        local rv = require "RVClientSP"
        local originalExit = rv.GetOutFromRV
        rv.GetOutFromRV = function(player)
            local record = F.playerData(player)
            if record and record.RoomType == F.type then F.exit(player); return end
            return originalExit(player)
        end
        local originalGenerator = UpdateGen
        UpdateGen = function(room, vehicleType, ...)
            if vehicleType ~= F.type then return originalGenerator(room, vehicleType, ...) end
        end
    end
end
Events.OnGameStart.Add(install)

local function context(playerNum, menu, worldObjects)
    local player = getSpecificPlayer(playerNum)
    local room = F.roomAt(player:getX(), player:getY(), player:getZ())
    if not room then return end
    local square = player:getSquare()
    for dx = -2, 2 do
        for dy = -2, 2 do
            local sq = getCell():getGridSquare(square:getX() + dx, square:getY() + dy, square:getZ())
            if sq then
                local moving = sq:getMovingObjects()
                for i = 0, moving:size() - 1 do
                    local animal = moving:get(i)
                    if instanceof(animal, "IsoAnimal") and player:DistToSquared(animal) <= 9 then
                        menu:addOption("Bring " .. animal:getFullName() .. " out of farm", player, function()
                            ISTimedActionQueue.add(ISFarmTrailerAction:new(player, "animalOut", nil, animal))
                        end)
                    end
                end
            end
        end
    end
end
Events.OnFillWorldObjectContextMenu.Add(context)

-- Use replicated part data so the driving client's physics receives the water load.
if isClient() then
    Events.EveryOneMinute.Add(function()
        local vehicles = getCell():getVehicles():iterator()
        while vehicles:hasNext() do
            local vehicle = vehicles:next()
            if F.isVehicle(vehicle) then
                local part = vehicle:getPartById("TrailerAnimalFood")
                local data = part:getModData()
                if data.FarmTrailerDryMass then F.applyMass(vehicle, data) end
            end
        end
    end)
end
