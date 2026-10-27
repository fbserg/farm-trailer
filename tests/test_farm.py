"""Portable behaviour tests with Lua, separate from the native engine gate."""
from pathlib import Path
import unittest
from lupa import LuaRuntime

ROOT = Path(__file__).resolve().parents[1] / "FarmTrailer/42/media/lua"

FIXTURE = r'''
local events = {}
Events = setmetatable({}, {__index=function(t,k)
    local handlers = {}
    local e = {Add=function(fn) handlers[#handlers+1]=fn end, handlers=handlers}
    rawset(t,k,e); return e
end})
function isClient() return false end
function isServer() return false end
function isMultiplayer() return false end
local data = {}
ModData = {getOrCreate=function(k) if not data[k] then data[k]={} end return data[k] end}
local hooks={handlers={}}
package.preload.RVHooks=function()return {register=function(flag,fn)hooks.handlers[flag]=fn end,emit=function(flag,ctx)if hooks.handlers[flag] then return hooks.handlers[flag](ctx) end end}end
local types = {normal={scripts={"Base.Van"},rooms={{x=22560,y=12360,z=0}},roomWidth=3,roomHeight=7}}
package.preload.RVVehicleTypes=function() return {VehicleTypes=types} end
local squares = {}
function key(x,y,z) return x .. ":" .. y .. ":" .. z end
function array(items)
    return {size=function() return #items end,get=function(_,i) return items[i+1] end,
        contains=function(_,v) for _,x in ipairs(items) do if x==v then return true end end return false end,
        iterator=function()local i=0;return {hasNext=function()return i<#items end,next=function()i=i+1;return items[i]end}end}
end
local cell = {getGridSquare=function(_,x,y,z) return squares[key(x,y,z)] end,getVehicles=function()return array({})end}
function getCell() return cell end
function setSquare(x,y,z,square) squares[key(x,y,z)] = square end
FluidType={Water="Water",TaintedWater="TaintedWater"}
IsoFlagType={water="water"}
function getNumActivePlayers() return 0 end
function instanceof(object,name) return object.class == name end
function sendRemoveItemFromContainer() end
function makeBarrel(amount)
    local object = {amount=amount,md={FarmTrailerWater="22560:12500"},capacity=400}
    function object:getModData() return self.md end
    function object:getFluidCapacity() return self.capacity end
    function object:getFluidAmount() return self.amount end
    function object:addFluid(kind,n) self.amount=self.amount+n; self.kind=kind end
    function object:sync() end
    return object
end
function installBarrels(a,b)
    local function sq(object) return {getObjects=function() return array({object}) end} end
    setSquare(22562,12502,0,sq(a));setSquare(22563,12502,0,sq(b))
end
function makeVehicle()
    local battery={charge=1,getCurrentUsesFloat=function(self)return self.charge end,setCurrentUsesFloat=function(self,n)self.charge=n end}
    local v={md={projectRV_uniqueId="farm-1"},speed=0,mass=500,initial=500,battery=battery,partData={}}
    function v:getScript() return {getFullName=function()return "Base.TrailerKI5livestock" end} end
    function v:getX() return 100 end;function v:getY() return 100 end;function v:getZ()return 0 end
    function v:getModData() return self.md end
    function v:getCurrentSpeedKmHour()return self.speed end
    function v:getTowingPartner() return nil end
    function v:getPartById() return {getInventoryItem=function()return battery end,getVehicle=function()return v end,getModData=function()return v.partData end} end
    function v:transmitPartUsedDelta()end
    function v:getInitialMass()return self.initial end
    function v:setInitialMass(n)self.initial=n end
    function v:updateTotalMass() self.mass=self.initial end
    function v:transmitPartModData()end
    function v:getMass()return self.mass end
    function v:setMass(n)self.mass=n end
    return v
end
function makePlayer()
    local p={x=22566,y=12503,z=0,md={projectRV_playerId="p1"},distance=4,hose=true}
    function p:getModData()return self.md end
    function p:getX()return self.x end;function p:getY()return self.y end;function p:getZ()return self.z end
    function p:setSitOnGround()end;function p:setSittingOnFurniture()end
    function p:setX(n)self.x=n end;function p:setLastX(n)end
    function p:setY(n)self.y=n end;function p:setLastY(n)end
    function p:setZ(n)self.z=n end;function p:setLastZ(n)end
    function p:DistToSquared()return self.distance end
    function p:getInventory()return {containsTypeRecurse=function()return p.hose end}end
    return p
end
'''

class FarmTests(unittest.TestCase):
    def setUp(self):
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        self.lua.execute(FIXTURE)
        self.lua.execute("package.path = " + repr(str(ROOT / "shared/?.lua")) + " .. ';' .. package.path")
        self.lua.execute((ROOT / "shared/FarmTrailer.lua").read_text())
        self.lua.execute((ROOT / "server/FarmTrailerServer.lua").read_text())
        self.lua.execute("F=FarmTrailer; room=F.rooms[1]; F.register()")

    def check(self, code):
        self.lua.execute(code)

    def test_registration_adds_only_livestock_type(self):
        self.check('local t=require("RVVehicleTypes").VehicleTypes; assert(t.normal.scripts[1]=="Base.Van"); assert(t[F.type].scripts[1]==F.script); assert(#t[F.type].rooms==38)')

    def test_pool_boundaries_do_not_link_neighbours(self):
        self.check('assert(F.roomAt(22560,12500,0)); assert(F.roomAt(22573,12541,0)); assert(not F.roomAt(22574,12541,0)); assert(not F.roomAt(22560,12542,0)); assert(not F.roomAt(22560,12500,1)); assert(F.roomAt(22620,12500,0)==F.rooms[2])')

    def test_pool_collision_fails(self):
        self.check('require("RVVehicleTypes").VehicleTypes.other={scripts={},rooms={{x=22561,y=12501,z=0}},roomWidth=2,roomHeight=2}; assert(not pcall(F.register))')

    def test_pool_collision_leaves_parent_registrations_unchanged(self):
        self.check('''local types=require("RVVehicleTypes").VehicleTypes;
        types.normal.scripts={"Base.Van",F.script};local farm=types[F.type];
        types.other={scripts={},rooms={{x=22561,y=12501,z=0}},roomWidth=2,roomHeight=2};
        setmetatable(types,{__pairs=function(t)local i=0;local keys={"normal","other"};
        return function()i=i+1;local k=keys[i];if k then return k,rawget(t,k)end end end});
        assert(not pcall(F.register));assert(types.normal.scripts[2]==F.script);
        assert(types[F.type]==farm)''')

    def test_legacy_entry_selects_saved_type_and_restores_registry(self):
        self.check('''local types=require("RVVehicleTypes").VehicleTypes;local v=makeVehicle();v.md.projectRV_type="normal";
        F.rvData().AssignedRooms={["farm-1"]={x=22560,y=12360,z=0}};
        local scripts=types.normal.scripts;local farms=types[F.type].scripts;
        F.withVehicleType(v,function()assert(types.normal.scripts[2]==F.script);assert(#types[F.type].scripts==0)end);
        assert(types.normal.scripts==scripts and types[F.type].scripts==farms);
        assert(not F.isFarmVehicle(v));assert(F.rvData().AssignedRooms["farm-1"].y==12360)''')

    def test_legacy_entry_error_restores_registry(self):
        self.check('''local t=require("RVVehicleTypes").VehicleTypes;local v=makeVehicle();v.md.projectRV_type="normal";
        local a,b=t.normal.scripts,t[F.type].scripts;
        local ok,err=pcall(F.withVehicleType,v,function()error("parent failed")end);assert(not ok and string.find(err,"parent failed"));
        assert(t.normal.scripts==a and t[F.type].scripts==b)''')

    def test_stale_room_type_inside_farm_uses_safe_exit(self):
        self.check('''p=makePlayer();local data=F.rvData();
        data.Players={p1={RoomType="normal",ActualRoom=room,VehicleId="farm-1"}};
        data.Vehicles={["farm-1"]={x=100,y=200,z=0}};
        assert(F.isFarmRecord(data.Players.p1));assert(F.exit(p));assert(p.x==100)''')

    def test_exit_removes_only_outside_zombies(self):
        self.check('''local function object(kind)local o={class=kind};function o:removeFromSquare()self.removed=true end;
        function o:removeFromWorld()self.worldRemoved=true end;return o end;
        local inside=object("IsoZombie");local outside=object("IsoZombie");local cow=object("IsoAnimal");local corpse=object("IsoDeadBody");
        local function square(list)return {getMovingObjects=function()return array(list)end,getDeadBody=function()return corpse end}end;
        setSquare(room.x+1,room.y+1,0,square({inside}));setSquare(room.x-1,room.y+1,0,square({outside,cow}));
        F.cleanOutsideZombies(room);assert(outside.removed and outside.worldRemoved);
        assert(not inside.removed and not cow.removed and not corpse.removed)''')

    def test_nested_farm_entry_does_not_inherit_legacy_registration(self):
        self.check('''local t=require("RVVehicleTypes").VehicleTypes;local old=makeVehicle();old.md.projectRV_type="normal";local new=makeVehicle();
        F.withVehicleType(old,function()
            assert(t.normal.scripts[2]==F.script);
            F.withVehicleType(new,function()assert(t[F.type].scripts[1]==F.script);assert(#t.normal.scripts==1)end);
            assert(t.normal.scripts[2]==F.script)
        end);assert(t[F.type].scripts[1]==F.script and #t.normal.scripts==1)''')

    def test_sp_recovery_intercepts_before_parent_cleanup(self):
        self.prepare_client()
        self.check('''function rv.recoverPlayerFromInterior(player)
            F.rvData().Players={p1={RoomType=F.type,ActualRoom=room,VehicleId="farm-1"}};return true end;
        p.x=room.x+6;p.y=room.y+3;F.rvData().Vehicles={["farm-1"]={x=100,y=200,z=0}};
        rv.GetOutFromRV(p);assert(not nativeExit);assert(p.x==100 and p.y==200)''')

    def prepare_boundary(self):
        self.check('''function boundarySquare(x,y)
            local sq={md={FarmTrailerBuilt=true},items={}};
            function sq:getX()return x end;function sq:getY()return y end;function sq:getZ()return 0 end;
            function sq:getRoom()return nil end;function sq:getModData()return self.md end;
            function sq:getObjects()return array(self.items)end;function sq:getFloor()return self.floor end;
            function sq:AddTileObject(o)self.items[#self.items+1]=o end;
            function sq:RecalcAllWithNeighbours()end;function sq:transmitModdata()end;
            return sq
        end
        function boundaryObject(sq,name,sprite)
            local o={md={},sprite=sprite,name=name};
            function o:getSquare()return sq end;function o:getName()return self.name end;
            function o:getModData()return self.md end;
            function o:getSprite()return {getName=function()return self.sprite end}end;
            function o:setSpriteFromName(n)self.sprite=n end;
            function o:transmitModData()end;function o:transmitUpdatedSpriteToClients()end;function o:transmitCompleteItemToClients()end;
            sq:AddTileObject(o);return o
        end
        IsoObject={new=function(sq,sprite,name)
            local o=boundaryObject(sq,name,sprite);table.remove(sq.items);return o end};
        sq=boundarySquare(room.x,room.y+8);sq.floor=boundaryObject(sq,"floor","soil");
        wall=boundaryObject(sq,"Farm wall","walls_exterior_wooden_01_40");wall.md.custom="keep"''')

    def test_original_boundary_upgrade_preserves_object_and_contents(self):
        self.prepare_boundary()
        self.check('''local original=wall;F.upgradeBoundary(sq);
        assert(wall==original and wall.md.custom=="keep" and wall.md.FarmTrailerBoundary);
        assert(wall.sprite==F.boundarySprites.west.name and #sq.items==2);
        F.upgradeBoundary(sq);assert(#sq.items==2)''')

    def test_legacy_fence_upgrade(self):
        self.prepare_boundary()
        self.check('''wall.name="Farm fence";wall.sprite="fencing_01_24";F.upgradeBoundary(sq);
        assert(wall.sprite==F.boundarySprites.west.name and wall.md.custom=="keep")''')

    def test_boundary_conflict_leaves_original_wall_and_player_object_unchanged(self):
        self.prepare_boundary()
        self.check('''local chair=boundaryObject(sq,"Player chair","chair");F.upgradeBoundary(sq);
        assert(wall.sprite=="walls_exterior_wooden_01_40" and not wall.md.FarmTrailerBoundary);
        assert(chair.sprite=="chair" and #sq.items==3 and sq.md.FarmTrailerBoundaryConflict)''')

    def test_outer_border_is_idempotent_and_refuses_player_construction(self):
        self.prepare_boundary()
        self.check('''local outside=boundarySquare(room.x-1,room.y+8);outside.floor=boundaryObject(outside,"floor","soil");
        F.upgradeBoundary(outside);F.upgradeBoundary(outside);assert(#outside.items==2);
        assert(outside.items[2].md.FarmTrailerBoundary);
        local occupied=boundarySquare(room.x-1,room.y+9);occupied.floor=boundaryObject(occupied,"floor","soil");
        local chair=boundaryObject(occupied,"Player chair","chair");F.upgradeBoundary(occupied);
        assert(#occupied.items==2 and not chair.md.FarmTrailerBoundary and occupied.md.FarmTrailerBoundaryConflict)''')

    def test_boundary_does_not_change_interior_or_other_farms(self):
        self.prepare_boundary()
        self.check('''assert(not F.boundaryAt(room.x+1,room.y+1,0));assert(not F.boundaryAt(room.x-2,room.y,0));
        assert(not F.boundaryAt(room.x,room.y,1));assert(F.boundaryAt(F.rooms[2].x-1,12500,0)==F.rooms[2]);
        assert(F.boundaryAt(room.x-1,room.y-1,0)==room)''')

    def test_pool_collision_in_outer_border_is_rejected(self):
        self.check('''require("RVVehicleTypes").VehicleTypes.other={scripts={},rooms={{x=room.x-1,y=room.y,z=0}},roomWidth=0,roomHeight=0};
        local ok,err=pcall(F.register);assert(not ok and string.find(err,"overlaps"))''')

    def test_sledge_protection_is_scoped_and_checks_completion(self):
        self.prepare_boundary()
        self.check('''F.upgradeBoundary(sq);
        ISDestroyStuffAction={isValid=function()return true end,complete=function()destroyed=true;return true end};
        ISDestroyCursor={canDestroy=function()return true end};
        package.loaded["TimedActions/ISDestroyStuffAction"]=true;package.loaded["BuildingObjects/ISDestroyCursor"]=true;
        F.installBoundaryProtection();assert(not ISDestroyStuffAction.isValid({item=wall}));
        assert(not ISDestroyStuffAction.complete({item=wall}) and not destroyed);
        assert(not ISDestroyCursor.canDestroy({},wall));assert(ISDestroyCursor.canDestroy({},sq.floor));
        assert(ISDestroyStuffAction.complete({item=sq.floor}) and destroyed)''')

    def test_pending_delivery_preserves_existing_water(self):
        self.check('a=makeBarrel(100);b=makeBarrel(200);installBarrels(a,b); F.state(room).pending=50;F.updateWater(room);assert(a.amount==150 and b.amount==200);assert(F.state(room).known==350 and F.state(room).pending==0);assert(a.kind=="TaintedWater")')

    def test_rain_overflow_never_exceeds_capacity(self):
        self.check('a=makeBarrel(390);b=makeBarrel(400);installBarrels(a,b); F.state(room).pending=40;F.updateWater(room); assert(a.amount==400 and b.amount==400);assert(F.state(room).pending==0)')

    def test_unloaded_water_is_not_reset(self):
        self.check('F.state(room).known=250;F.state(room).pending=80;F.updateWater(room); assert(F.state(room).known==250 and F.state(room).pending==80)')

    def test_destroyed_collectors_are_not_recreated(self):
        self.check('setSquare(22562,12502,0,{getObjects=function()return array({})end});setSquare(22563,12502,0,{getObjects=function()return array({})end});F.state(room).pending=80;F.updateWater(room);assert(F.state(room).capacity==0 and F.state(room).pending==0)')

    def prepare_pump(self):
        self.check('''p=makePlayer();p.x=100;p.y=100;v=makeVehicle();
        F.rvData()["AssignedRooms"..F.type]={["farm-1"]=room};
        setSquare(100,101,0,{getProperties=function()return {has=function(_,flag)return flag=="water"end}end})''')

    def test_pump_limits_volume_and_consumes_battery(self):
        self.prepare_pump()
        self.check('F.state(room).known=795;assert(F.pump(p,v)==5);assert(F.state(room).pending==5);assert(math.abs(v.battery.charge-0.99875)<0.00001);assert(v.mass==1300);assert(F.pump(p,v)==0)')

    def test_pump_rejects_movement_distance_hose_and_empty_battery(self):
        self.prepare_pump()
        self.check('v.speed=1;assert(F.pump(p,v)==0);v.speed=0;p.distance=26;assert(F.pump(p,v)==0);p.distance=4;p.hose=false;assert(F.pump(p,v)==0);p.hose=true;v.battery.charge=0;assert(F.pump(p,v)==0);assert(F.state(room).pending==0)')

    def test_pump_requires_real_nearby_water(self):
        self.prepare_pump()
        self.check('setSquare(100,101,0,nil);assert(F.pump(p,v)==0)')

    def test_repeated_mass_updates_do_not_accumulate(self):
        self.check('v=makeVehicle();F.state(room).known=300;F.updateMass(v,room);F.updateMass(v,room);assert(v.mass==800)')

    def test_exit_preserves_contents_and_clears_only_player_assignment(self):
        self.check('''p=makePlayer();local data=F.rvData();
        data.Players={p1={RoomType=F.type,ActualRoom=room,VehicleId="farm-1"},p2={RoomType=F.type}};
        data.Vehicles={["farm-1"]={x=100,y=200,z=0}};
        assert(F.exit(p));assert(p.x==100 and p.y==200);assert(data.Players.p1==nil and data.Players.p2);
        assert(not F.exit(p))''')

    def test_spoofed_exit_from_outside_farm_is_rejected(self):
        self.check('p=makePlayer();p.x=1;F.rvData().Players={p1={RoomType=F.type,ActualRoom=room}};assert(not F.exit(p))')

    def test_exit_just_outside_fence_keeps_farm_exit_path(self):
        self.check('''p=makePlayer();p.x=room.x-1;local data=F.rvData();
        data.Players={p1={RoomType=F.type,ActualRoom=room,VehicleId="farm-1"}};
        data.Vehicles={["farm-1"]={x=100,y=200,z=0}};assert(F.exit(p));assert(p.x==100)''')

    def test_rejected_farm_exit_never_calls_parent_cleanup(self):
        self.check('''function isMultiplayer()return true end;local called=false;
        RVServer={GetOutFromRV=function()called=true end};UpdateGen=function()end;FillRainCollectorsInRoom=function()end;
        F.installServerHooks();p=makePlayer();p.x=1;F.rvData().Players={p1={RoomType=F.type,ActualRoom=room}};
        RVServer.GetOutFromRV(p);assert(not called)''')

    def test_maintenance_accepts_native_vehicle_set(self):
        self.check('''getCell().getVehicles=function()return {iterator=function()return {hasNext=function()return false end}end}end;
        Events.EveryOneMinute.handlers[1]()''')

    def prepare_client(self):
        self.prepare_pump()
        self.check('''package.loaded["TimedActions/ISFarmTrailerAction"]=true;
        rv={GetOutFromRV=function()nativeExit=true end};package.preload.RVClientSP=function()return rv end;
        UpdateGen=function()nativeGenerator=true end;
        function p:getPlayerNum()return 0 end;function v:getAnimals()return array({})end;
        menu={slices={}};function menu:addSlice(text,texture,command,...)self.slices[#self.slices+1]={text=text,command={command,...}}end;
        function getText(key)return key end;function getTexture()return nil end;function getPlayerRadialMenu()return menu end;
        ISVehicleMenu={getVehicleToInteractWith=function()return v end,showRadialMenu=function(player)
        menu.slices={};if not suppressEntry then menu:addSlice("ContextMenu_GetInToRV",nil,function()nativeEntry=true end,player)end end}''')
        self.lua.execute((ROOT / "client/ZZFarmTrailerClient.lua").read_text())
        self.check("Events.OnGameStart.handlers[1]()")

    def test_client_reuses_parent_entry_and_only_skips_farm_generator(self):
        self.prepare_client()
        self.check('''ISVehicleMenu.showRadialMenu(p);assert(#menu.slices==3);F.enterFromMenu(p,v);assert(nativeEntry);
        local hooks=require("RVHooks");assert(hooks.emit("postEnter",{typeKey=F.type})==false);assert(hooks.emit("postEnter",{typeKey="normal"})~=false)''')

    def test_client_does_not_add_farm_controls_to_other_vehicles(self):
        self.prepare_client()
        self.check('''function v:getScript()return {getFullName=function()return "Base.Van"end}end;
        ISVehicleMenu.showRadialMenu(p);assert(#menu.slices==1 and menu.slices[1].text=="ContextMenu_GetInToRV")''')

    def test_client_forgets_entry_when_next_menu_has_no_entry(self):
        self.prepare_client()
        self.check('''ISVehicleMenu.showRadialMenu(p);assert(F.entryMenus[0]);
        suppressEntry=true;function v:getAnimals()return array({{}})end;
        ISVehicleMenu.showRadialMenu(p);assert(F.entryMenus[0]==nil);assert(#menu.slices==2);
        function v:getScript()return {getFullName=function()return "Base.Van"end}end;
        ISVehicleMenu.showRadialMenu(p);assert(F.entryMenus[0]==nil)''')

    def test_parent_hooks_change_only_farm_type(self):
        self.check('''function isMultiplayer()return true end;calls={};RVServer={GetOutFromRV=function()calls.exit=true end};
        GetInToRV=function()calls.enter=true end;F.installServerHooks();
        local hooks=require("RVHooks");assert(hooks.emit("postEnter",{typeKey=F.type})==false);
        assert(hooks.emit("postEnter",{typeKey="normal"})~=false);
        RVServer.GetOutFromRV(makePlayer());assert(calls.exit)''')

    def test_legacy_menu_and_entry_use_saved_type_when_farm_pool_is_full(self):
        self.prepare_client()
        self.check('''v.md.projectRV_type="normal";local t=require("RVVehicleTypes").VehicleTypes;
        local function registered()for k,d in pairs(t)do for _,script in ipairs(d.scripts)do if script==F.script then return k end end end end;
        -- Exercise the wrapper with a parent-shaped capacity check and callback.
        F.entryMenus={};local old=ISVehicleMenu.showRadialMenu;
        ISVehicleMenu.showRadialMenu=function(player)
            menu.slices={};if registered()=="normal" then menu:addSlice("ContextMenu_GetInToRV",nil,function()assert(registered()=="normal");nativeEntry=true end,player) end
        end;
        Events.OnGameStart.handlers[1]();ISVehicleMenu.showRadialMenu(p);
        assert(#menu.slices==1);menu.slices[1].command[1]();assert(nativeEntry);
        assert(t[F.type].scripts[1]==F.script and #t.normal.scripts==1)''')

    def test_release_requires_matching_assignment_and_preserves_interrupted_carrier(self):
        self.check('''p=makePlayer();local item={class="AnimalInventoryItem",md={FarmTrailerTransfer="farm",FarmTrailerTransferVehicle="farm-1"}};
        function item:getModData()return self.md end;p.item=item;
        function p:getPrimaryHandItem()return self.item end;
        function p:setPrimaryHandItem(v)self.item=v end;function p:setSecondaryHandItem()end;
        local inv={Remove=function()removed=true end};function p:getInventory()return inv end;
        local square={getX=function()return 22566 end,getY=function()return 12503 end,getZ=function()return 0 end,
            getModData=function()return {FarmTrailerBuilt=true}end,AddWorldInventoryItem=function()released=(released or 0)+1;return {}end};
        function p:getSquare()return square end;
        F.releaseCargo(p);assert(p.item==item and not released);
        F.rvData().Players={p1={RoomType=F.type,ActualRoom=room,VehicleId="other"}};
        F.releaseCargo(p);assert(p.item==item and not released);
        F.rvData().Players.p1.VehicleId="farm-1";F.releaseCargo(p);
        assert(p.item==nil and released==1 and removed);F.releaseCargo(p);assert(released==1)''')

    def test_native_release_failure_keeps_carrier(self):
        self.check('''p=makePlayer();local item={class="AnimalInventoryItem",getModData=function()return {FarmTrailerTransfer="outside"}end};
        function p:getPrimaryHandItem()return item end;
        function p:getSquare()return {getX=function()return 100 end,getY=function()return 100 end,getZ=function()return 0 end,AddWorldInventoryItem=function()return nil end}end;
        local ok,err=pcall(F.releaseCargo,p);assert(not ok and string.find(err,"Native animal release failed"));assert(p:getPrimaryHandItem()==item)''')

    def test_animal_completion_rechecks_lock_and_crosses_only_after_pickup(self):
        self.check('''ISBaseTimedAction={derive=function(self)return setmetatable({},{__index=self})end};
        package.loaded["TimedActions/ISBaseTimedAction"]=true;
        package.loaded["TimedActions/Animals/ISRemoveAnimalFromTrailer"]=true;
        package.loaded["TimedActions/Animals/ISPickupAnimal"]=true;
        p=makePlayer();p.x=100;p.y=100;v=makeVehicle();v.locked=true;
        function v:isTrunkLocked()return self.locked end;
        animal={class="IsoAnimal"};local present=true;
        function v:getAnimals()return {contains=function()return present end}end;
        item={class="AnimalInventoryItem",md={}};function item:getModData()return self.md end;
        function p:getPrimaryHandItem()return self.item end;
        function p:getSecondaryHandItem()return nil end;
        ISRemoveAnimalFromTrailer={new=function()return {complete=function()
            assert(not crossed);picked=(picked or 0)+1;p.item=item;present=false;return true end}end};
        function isServer()return true end;
        function GetInToRV(player,vehicle)assert(picked==1);crossed=true end;
        function sendItemStats()end''')
        self.lua.execute((ROOT / "shared/TimedActions/ISFarmTrailerAction.lua").read_text())
        self.check('''local a=setmetatable({character=p,vehicle=v,animal=animal,operation="animalIn"},{__index=ISFarmTrailerAction});
        assert(not a:complete() and not picked and not crossed);
        v.locked=false;p.distance=26;assert(not a:complete() and not picked);
        p.distance=4;assert(a:complete() and picked==1 and crossed);
        assert(item.md.FarmTrailerTransferVehicle=="farm-1");
        assert(not a:complete() and picked==1)''')

    def test_changed_radial_does_not_enter_wrong_trailer(self):
        self.prepare_client()
        self.check('''ISVehicleMenu.showRadialMenu(p);local other=makeVehicle();
        assert(not F.enterFromMenu(p,other));assert(not nativeEntry)''')


if __name__ == "__main__":
    unittest.main(verbosity=2)
