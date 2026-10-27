"""Carrier preservation checks for interrupted farm crossings."""
import unittest

import test_farm


class AnimalTransferTests(unittest.TestCase):
    def setUp(self):
        fixture = test_farm.FarmTests()
        fixture.setUp()
        self.fixture = fixture
        self.lua = fixture.lua
        self.lua.execute(r'''
        ISBaseTimedAction={derive=function(self)return setmetatable({},{__index=self})end}
        package.loaded["TimedActions/ISBaseTimedAction"]=true
        package.loaded["TimedActions/Animals/ISRemoveAnimalFromTrailer"]=true
        package.loaded["TimedActions/Animals/ISPickupAnimal"]=true
        p=makePlayer();v=makeVehicle()
        function p:getPrimaryHandItem()return self.primary end
        function p:getSecondaryHandItem()return self.secondary end
        function v:isTrunkLocked()return false end
        animal={class="IsoAnimal"}
        function animal:getSquare()return {} end
        function animal:getX()return p.x end
        function animal:getY()return p.y end
        function animal:getZ()return p.z end
        function v:getAnimals()return array({animal})end
        carrier={class="AnimalInventoryItem",md={FarmTrailerTransfer="farm",FarmTrailerTransferVehicle="farm-1"}}
        function carrier:getModData()return self.md end
        local function pickup()
            -- Both native pickup completions call forceDropHeavyItems before equipping.
            dropped=p.primary or p.secondary
            picked=true
            p.primary={class="AnimalInventoryItem",getModData=function()return {}end}
            return true
        end
        ISRemoveAnimalFromTrailer={new=function()return {complete=pickup}end}
        ISPickupAnimal={new=function()return {complete=pickup}end}
        function isServer()return true end
        function GetInToRV()crossed=true end
        F.exit=function()crossed=true;return true end
        F.awaitCargo=function()end
        function sendItemStats()end
        ''')
        self.lua.execute((test_farm.ROOT / "shared/TimedActions/ISFarmTrailerAction.lua").read_text())

    def test_existing_carrier_stays_in_either_hand_for_both_directions(self):
        self.lua.execute(r'''
        for _,operation in ipairs({"animalIn","animalOut"})do
            for _,hand in ipairs({"primary","secondary"})do
                p.x=operation=="animalIn" and 100 or room.x+6
                p.y=operation=="animalIn" and 100 or room.y+3
                p.primary=nil;p.secondary=nil;p[hand]=carrier
                picked=nil;dropped=nil;crossed=nil
                local action=setmetatable({character=p,vehicle=v,animal=animal,operation=operation},{__index=ISFarmTrailerAction})
                assert(not action:complete(),operation.." replaced the "..hand.." carrier")
                assert(p[hand]==carrier and not picked and not dropped and not crossed)
                assert(carrier.md.FarmTrailerTransferVehicle=="farm-1")
            end
        end
        ''')

    def test_normal_transfer_still_completes(self):
        self.lua.execute(r'''
        for _,operation in ipairs({"animalIn","animalOut"})do
            p.x=operation=="animalIn" and 100 or room.x+6
            p.y=operation=="animalIn" and 100 or room.y+3
            p.primary=nil;p.secondary=nil;picked=nil;crossed=nil
            local action=setmetatable({character=p,vehicle=v,animal=animal,operation=operation},{__index=ISFarmTrailerAction})
            assert(action:complete() and picked and crossed)
        end
        ''')

    def test_menu_explains_why_a_second_transfer_is_blocked(self):
        self.fixture.prepare_client()
        self.lua.execute(r'''
        function p:getPrimaryHandItem()return carrier end
        function p:getSecondaryHandItem()return carrier end
        function animal:getFullName()return "Cow"end
        function v:getAnimals()return array({animal})end
        function getMouseX()return 0 end
        function getMouseY()return 0 end
        ISContextMenu={get=function()return {addOption=function(_,text,player,callback)selected=callback end}end}
        HaloTextHelper={addBadText=function(player,text)assert(player==p);feedback=text end}
        ISTimedActionQueue={add=function()queued=true end}
        ISVehicleMenu.showRadialMenu(p)
        local transfer
        for _,slice in ipairs(menu.slices)do
            if slice.text=="Bring livestock into farm" then transfer=slice.command[1] end
        end
        assert(transfer,"Livestock transfer menu missing")
        transfer()
        selected()
        assert(feedback=="Place the animal you carry before moving another.")
        assert(not queued and p:getPrimaryHandItem()==carrier)
        ''')


if __name__ == "__main__":
    unittest.main(verbosity=2)
