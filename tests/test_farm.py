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
        self.check('''ISVehicleMenu.showRadialMenu(p);assert(#menu.slices==2);F.enterFromMenu(p);assert(nativeEntry);
        UpdateGen(room,F.type,true);assert(not nativeGenerator);UpdateGen(room,"normal",true);assert(nativeGenerator)''')

    def test_client_does_not_add_farm_controls_to_other_vehicles(self):
        self.prepare_client()
        self.check('''function v:getScript()return {getFullName=function()return "Base.Van"end}end;
        ISVehicleMenu.showRadialMenu(p);assert(#menu.slices==1 and menu.slices[1].text=="ContextMenu_GetInToRV")''')

    def test_client_forgets_entry_when_next_menu_has_no_entry(self):
        self.prepare_client()
        self.check('''ISVehicleMenu.showRadialMenu(p);assert(F.entryMenus[0]);
        suppressEntry=true;function v:getAnimals()return array({{}})end;
        ISVehicleMenu.showRadialMenu(p);assert(F.entryMenus[0]==nil);assert(#menu.slices==1);
        function v:getScript()return {getFullName=function()return "Base.Van"end}end;
        ISVehicleMenu.showRadialMenu(p);assert(F.entryMenus[0]==nil)''')

    def test_parent_hooks_change_only_farm_type(self):
        self.check('''function isMultiplayer()return true end;calls={};RVServer={GetOutFromRV=function()calls.exit=true end};
        UpdateGen=function()calls.gen=true end;FillRainCollectorsInRoom=function()calls.water=true end;
        F.installServerHooks();UpdateGen({vType=F.type});FillRainCollectorsInRoom({vType=F.type});assert(not calls.gen and not calls.water);
        UpdateGen({vType="normal"});FillRainCollectorsInRoom({vType="normal"});assert(calls.gen and calls.water);
        RVServer.GetOutFromRV(makePlayer());assert(calls.exit)''')

if __name__ == "__main__":
    unittest.main(verbosity=2)
