// EnergyPlus, blablabla, very very very long copyright
// with a lot of lines
// etc, blablabla/

// EnergyPlus::AirTerminal SingleDuct Unit Tests
// AirTerminal:SingleDuct:ConstantVolume:Reheat
// AirTerminal:SingleDuct:ConstantVolume:FourPipeInduction
// AirTerminal:SingleDuct:VAV:HeatAndCool:Reheat
// AirTerminal:SingleDuct:VAV:Reheat:VariableSpeedFan

// Google Test Headers
#include <gtest/gtest.h>

#include "Fixtures/EnergyPlusFixture.hh"
#include <EnergyPlus/Data/EnergyPlusData.hh>
#include <EnergyPlus/ZoneAirLoopEquipmentManager.hh>

// EnergyPlus Headers
using namespace EnergyPlus::DataAirLoop;
using namespace EnergyPlus::DataHeatBalFanSys;

namespace EnergyPlus {

TEST_F(EnergyPlusFixture, DelimitedStringTest)
{

    bool ErrorsFound(false);

    std::string const idf_objects = delimited_string({
        "Zone,",
        "  Zone2;                   !- Name",

        "Schedule:Compact,",
        "  FanAndCoilAvailSched,    !- Name",
        "  Fraction,                !- Schedule Type Limits Name",
        "  Through: 12/31,          !- Field 1",
        "  For: AllDays,            !- Field 2",
        "  Until: 24:00,            !- Field 3",
        "  1.0;                     !- Field 4",

        "! An IDF comment",

        // A C++ comment, that happens
        "Zone,",
        "  West Zone,               !- Name",
        "  0.0,                     !- Direction of Relative North {deg}",
        "  0.0,                     !- X Origin {m}",
        "  0.0,                     !- Y Origin {m}",
        "  0.0,                     !- Z Origin {m}", // An inline C++ comment, that happens
        "  1,                       !- Type",
        "  1,                       !- Multiplier",
        "  Autocalculate,           !- Ceiling Height {m}",
        "  Autocalculate;           !- Volume {m3}",

        "Zone,",
        // An in-object comment, that happens
        "  Zone3;                   !- Name",
    });

    ASSERT_TRUE(process_idf(idf_objects));

    state->dataGlobal->TimeStepsInHour = 1;    // must initialize this to get schedules initialized
    state->dataGlobal->MinutesInTimeStep = 60; // must initialize this to get schedules initialized

    state->init_state(*state);

    GetZoneData(*state, ErrorsFound);
    ASSERT_FALSE(ErrorsFound);

    GetZoneEquipmentData(*state);
    GetZoneAirLoopEquipment(*state);
    GetSysInput(*state);

    EXPECT_EQ("AirTerminal:SingleDuct:ConstantVolume:Reheat", state->dataSingleDuct->sd_airterminal(1).sysType); // AT SD VAV Reheat Type
    EXPECT_EQ("REHEAT ZONE 1", state->dataSingleDuct->sd_airterminal(1).SysName);                                // AT SD VAV Reheat Name
    EXPECT_GT(state->dataSingleDuct->sd_airterminal(1).ReheatControlNode, 0); // none zero integer node index is expected

    std::string const error_string = delimited_string({
        "   ** Severe  ** getAirLoopMixer: Node Connection Error in AirLoopHVAC:DedicatedOutdoorAirSystem = AIRLOOPHVAC DOAS. Inlet node of "
        "DOAS_COOLC as current component is not same as the outlet node of DOAS OA HUMIDIFIER "
        "as previous component",
        "   **   ~~~   ** The inlet node name = OUTSIDE AIR INLET NODE 1, and the outlet node name = AIRLOOPDOASSPLITTERINLET.",
        "   ** Severe  ** Inlet node (OA SUPPLY FAN OUTLET NODE) is not one of OutdoorAir:Node in AirLoopHVAC:OutdoorAirSystem:EquipmentList = "
        "AIRLOOPHVAC DOAS",
    });
    EXPECT_TRUE(compare_err_stream(error_string, true));
}

TEST_F(EnergyPlusFixture, RawStringLiterral)
{

    std::string_view constexpr idf_objects = R"IDF(

SetpointManager:Scheduled,
  Cooling Coil Setpoint Manager,  !- Name
  Temperature,             !- Control Variable
  Always 20C,              !- Schedule Name
  Zone 2 Inlet Node;       !- Setpoint Node or NodeList Name

Curve:Quadratic,
  Quadratic,               !- Name
  0.8,                     !- Coefficient1 Constant
  0.2,                     !- Coefficient2 x
  0.0,                     !- Coefficient3 x**2
  0.5,                     !- Minimum Value of x
  1.5;                     !- Maximum Value of x

    )IDF";

    ASSERT_TRUE(process_idf(idf_objects));
    state->init_state(*state);
}
