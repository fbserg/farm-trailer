"""Water feedback authority and snapshot behavior."""
import unittest
import test_farm as farm

class WaterTests(unittest.TestCase):
    setUp = farm.FarmTests.setUp
    check = farm.FarmTests.check
    prepare_pump = farm.FarmTests.prepare_pump
    prepare_client = farm.FarmTests.prepare_client

    def notice_fixture(self):
        self.check('''p=makePlayer();v=makeVehicle();F.rvData().Players={p1={RoomType=F.type,ActualRoom=room,VehicleId="farm-1"}};
        notices={};HaloTextHelper={addBadText=function(player,text)notices[#notices+1]={player=player,text=text}end};
        Events.OnTick.Remove=function(fn)for i,h in ipairs(Events.OnTick.handlers)do if h==fn then table.remove(Events.OnTick.handlers,i);break end end end;
        function tick()local copy={};for i,h in ipairs(Events.OnTick.handlers)do copy[i]=h end;for _,h in ipairs(copy)do h()end end;
        ctx={player=p,vehicle=v,room=room,typeKey=F.type,side="SP"}''')

    def test_snapshot_unknown_and_threshold(self):
        self.check('''v=makeVehicle();assert(F.waterStatusText(v)=="Farm water: enter farm to check");
        v.partData.FarmTrailerWaterObserved=true;v.partData.FarmTrailerWaterMass=159.9;
        assert(F.waterStatusText(v)=="Farm water: 159 / 800 L (LOW) (snapshot)");
        v.partData.FarmTrailerWaterMass=160;assert(F.waterStatusText(v)=="Farm water: 160 / 800 L (snapshot)")''')

    def test_loaded_measurement_replicates_observation(self):
        self.check('''v=makeVehicle();installBarrels(makeBarrel(100),makeBarrel(50));F.updateWater(room);F.updateMass(v,room);
        assert(v.partData.FarmTrailerWaterObserved and v.partData.FarmTrailerWaterMass==150)''')

    def test_unloaded_snapshot_remains_unchanged(self):
        self.check('''v=makeVehicle();F.state(room).known=300;F.state(room).pending=20;F.state(room).observed=true;
        F.updateWater(room);F.updateMass(v,room);assert(v.partData.FarmTrailerWaterMass==320 and v.partData.FarmTrailerWaterObserved)''')

    def test_loaded_entry_notifies_once(self):
        self.notice_fixture()
        self.check('''installBarrels(makeBarrel(70),makeBarrel(80));F.awaitWaterNotice(ctx);tick();tick();assert(#notices==1 and notices[1].player==p);assert(#Events.OnTick.handlers==0)''')

    def test_delayed_entry_waits_for_real_water(self):
        self.notice_fixture()
        self.check('''F.awaitWaterNotice(ctx);tick();assert(#notices==0);installBarrels(makeBarrel(100),makeBarrel(100));tick();assert(#notices==0 and #Events.OnTick.handlers==0)''')

    def test_timeout_never_warns_from_unloaded_zero(self):
        self.notice_fixture()
        self.check('''F.awaitWaterNotice(ctx);for i=1,600 do tick()end;assert(#notices==0 and #Events.OnTick.handlers==0)''')

    def test_exit_cancels_notice(self):
        self.notice_fixture()
        self.check('''F.awaitWaterNotice(ctx);F.rvData().Players.p1=nil;installBarrels(makeBarrel(0),makeBarrel(0));tick();assert(#notices==0)''')

    def test_reentry_invalidates_previous_callback(self):
        self.notice_fixture()
        self.check('''F.awaitWaterNotice(ctx);F.awaitWaterNotice(ctx);installBarrels(makeBarrel(0),makeBarrel(0));tick();assert(#notices==1)''')

    def test_client_hook_never_requests_authoritative_notice(self):
        self.check('''function isClient()return true end;F.awaitWaterNotice=function()error("client cannot inspect server water")end;
        assert(require("RVHooks").emit("postEnter",{typeKey=F.type,side="client"})==false)''')

    def test_server_notice_targets_entering_online_player(self):
        self.notice_fixture()
        self.check('''function isServer()return true end;function p:getOnlineID()return 17 end;
        function sendServerCommand(player,module,command,args)sent={player=player,module=module,command=command,args=args}end;
        installBarrels(makeBarrel(20),makeBarrel(30));F.awaitWaterNotice(ctx);tick();
        assert(#notices==0 and sent.player==p and sent.args.onlineID==17 and sent.args.amount==50)''')

    def test_exterior_status_requires_no_hose(self):
        self.prepare_client()
        self.check('''p.hose=false;ISVehicleMenu.showRadialMenu(p);assert(#menu.slices==2);
        assert(menu.slices[2].text=="Farm water: enter farm to check" and menu.slices[2].command[1]==nil)''')

    def test_client_command_resolves_online_target(self):
        self.prepare_client()
        self.check('''notices={};HaloTextHelper={addBadText=function(player,text)notices[#notices+1]={player=player,text=text}end};
        function getPlayerByOnlineID(id)assert(id==17);return p end;
        for _,fn in ipairs(Events.OnServerCommand.handlers)do fn("FarmTrailer","waterLow",{onlineID=17,amount=50})end;
        assert(#notices==1 and notices[1].player==p)''')
