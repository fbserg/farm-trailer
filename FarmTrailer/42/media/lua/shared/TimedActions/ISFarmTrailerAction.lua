require "TimedActions/ISBaseTimedAction"
require "TimedActions/Animals/ISRemoveAnimalFromTrailer"
require "TimedActions/Animals/ISPickupAnimal"
local F = require "FarmTrailer"
ISFarmTrailerAction = ISBaseTimedAction:derive("ISFarmTrailerAction")

function ISFarmTrailerAction:isValid()
    if self.operation == "pump" then return F.pumpReady(self.character, self.vehicle) end
    if self.operation == "animalIn" then
        return F.isVehicle(self.vehicle) and self.character:DistToSquared(self.vehicle) <= 25
            and math.abs(self.vehicle:getCurrentSpeedKmHour()) <= 0.1
    end
    local room = F.roomAt(self.character:getX(), self.character:getY(), self.character:getZ())
    return room ~= nil and self.animal and self.character:DistToSquared(self.animal) <= 9
end

function ISFarmTrailerAction:getDuration()
    if self.character:isTimedActionInstant() then return 1 end
    return self.operation == "pump" and 150 or 100
end

function ISFarmTrailerAction:complete()
    if self.operation == "pump" then return F.pump(self.character, self.vehicle) > 0 end
    if self.operation == "animalIn" then
        if not self.vehicle:getAnimals():contains(self.animal) then return false end
        local action = ISRemoveAnimalFromTrailer:new(self.character, self.vehicle, self.animal, true)
        if not action:complete() then return false end
    else
        if not self.animal:getSquare() then return false end
        local action = ISPickupAnimal:new(self.character, self.animal)
        if not action:complete() then return false end
    end
    local item = self.character:getPrimaryHandItem()
    assert(item and instanceof(item, "AnimalInventoryItem"), "Native livestock handoff failed")
    item:getModData().FarmTrailerTransfer = self.operation == "animalIn" and "farm" or "outside"
    sendItemStats(item)
    F.awaitCargo(self.character)
    return true
end

function ISFarmTrailerAction:perform()
    ISBaseTimedAction.perform(self)
    if self.operation == "animalIn" then F.enterFromMenu(self.character) end
    if self.operation == "animalOut" then F.requestExit(self.character) end
end

function ISFarmTrailerAction:new(character, operation, vehicle, animal)
    local o = ISBaseTimedAction.new(self, character)
    o.operation, o.vehicle, o.animal = operation, vehicle, animal
    o.stopOnWalk, o.stopOnRun = true, true
    o.maxTime = o:getDuration()
    return o
end
