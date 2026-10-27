local F = FarmTrailer

-- These IDs are part of saved worlds. Never renumber or reuse them.
F.boundarySprites = {
    north = {name = "FarmTrailerBoundaryNorth", id = 1894200001, texture = "walls_exterior_wooden_01_41"},
    west = {name = "FarmTrailerBoundaryWest", id = 1894200002, texture = "walls_exterior_wooden_01_40"},
    outer = {name = "FarmTrailerBoundaryOuter", id = 1894200003, texture = "blends_natural_01_16"},
}

function F.registerBoundarySprites()
    local manager = IsoSpriteManager.instance
    for kind, def in pairs(F.boundarySprites) do
        local existing = manager:getSprite(def.id)
        assert(not existing or existing:getName() == def.name, "Farm Trailer boundary sprite ID collision")
        local sprite = existing or manager:AddSprite(def.name, def.id)
        sprite:LoadSingleTexture(def.texture)
        sprite:setName(def.name)
        local props = sprite:getProperties()
        props:set(IsoFlagType.CantClimb)
        props:set(IsoFlagType.burntOut)
        if kind == "outer" then
            props:set(IsoFlagType.solidtrans)
            props:set(IsoFlagType.invisible)
        else
            props:set(kind == "north" and IsoFlagType.collideN or IsoFlagType.collideW)
            props:set(kind == "north" and IsoFlagType.WallN or IsoFlagType.WallW)
            props:set(kind == "north" and IsoFlagType.cutN or IsoFlagType.cutW)
        end
    end
end
-- OnInitWorld runs before the engine clears the sprite manager. Register after
-- tile definitions load, before saved world objects resolve their sprite IDs.
Events.OnLoadedTileDefinitions.Add(F.registerBoundarySprites)

function F.boundaryAt(x, y, z)
    if z ~= 0 or y < 12499 or y > 12542 then return nil end
    local room = F.rooms[math.floor((x - 22559) / 60) + 1]
    if not room or x < room.x - 1 or x > room.x + 14 then return nil end
    local dx, dy = x - room.x, y - room.y
    if dx == -1 or dx == 14 or dy == -1 or dy == 42 then return room, "outer" end
    if dx == 0 or dx == 13 or dy == 0 or dy == 41 then return room, "wall" end
end

function F.isBoundary(object)
    if not object or not object:getSquare() then return false end
    local sq = object:getSquare()
    return F.boundaryAt(sq:getX(), sq:getY(), sq:getZ()) ~= nil
        and object:getModData().FarmTrailerBoundary == true
end

-- The native cursor and timed action are separate paths. Protect both, including
-- actions already queued before a square was upgraded. Other objects delegate.
function F.installBoundaryProtection()
    require "TimedActions/ISDestroyStuffAction"
    local valid, complete = ISDestroyStuffAction.isValid, ISDestroyStuffAction.complete
    ISDestroyStuffAction.isValid = function(self, ...)
        if F.isBoundary(self.item) then return false end
        return valid(self, ...)
    end
    ISDestroyStuffAction.complete = function(self, ...)
        if F.isBoundary(self.item) then return false end
        return complete(self, ...)
    end
    if not isServer() then
        require "BuildingObjects/ISDestroyCursor"
        local original = ISDestroyCursor.canDestroy
        ISDestroyCursor.canDestroy = function(self, object, ...)
            if F.isBoundary(object) then return false end
            return original(self, object, ...)
        end
    end
end
Events.OnInitWorld.Add(F.installBoundaryProtection)
return F
