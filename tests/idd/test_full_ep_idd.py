from pathlib import Path

from energyplus_parser.idd.idd_file import IddFile


def test_full_ep_idd():
    idd_path = Path('~/Software/Others/EnergyPlus/idd/Energy+.idd.in').expanduser()
    idd_file = IddFile.load(path=idd_path)

    assert len(idd_file.objects) == 859
    assert idd_file.groups() == {
        '',
        'Advanced Construction, Surface, Zone Concepts',
        'Air Distribution',
        'AirflowNetwork',
        'Coils',
        'Compliance Objects',
        'Condenser Equipment and Heat Exchangers',
        'Controllers',
        'Daylighting',
        'Demand Limiting Controls',
        'Detailed Ground Heat Transfer',
        'Economics',
        'Electric Load Center-Generator Specifications',
        'Energy Management System (EMS)',
        'Evaporative Coolers',
        'Exterior Equipment',
        'External Interface',
        'Fans',
        'Fluid Properties',
        'General Data Entry',
        'HVAC Design Objects',
        'HVAC Templates',
        'Heat Recovery',
        'Humidifiers and Dehumidifiers',
        'Hybrid Model',
        'Internal Gains',
        'Location and Climate',
        'Node-Branch Management',
        'Non-Zone Equipment',
        'Operational Faults',
        'Output Reporting',
        'Parametrics',
        'Performance Curves',
        'Performance Tables',
        'Plant Heating and Cooling Equipment',
        'Plant-Condenser Control',
        'Plant-Condenser Flow Control',
        'Plant-Condenser Loops',
        'Pumps',
        'Python Plugin System',
        'Refrigeration',
        'Room Air Models',
        'Schedules',
        'Setpoint Managers',
        'Simulation Parameters',
        'Solar Collectors',
        'Surface Construction Elements',
        'System Availability Managers',
        'Thermal Zones and Surfaces',
        'Unitary Equipment',
        'User Defined HVAC and Plant Component Models',
        'Variable Refrigerant Flow Equipment',
        'Water Heaters and Thermal Storage',
        'Water Systems',
        'Zone Airflow',
        'Zone HVAC Air Loop Terminal Units',
        'Zone HVAC Controls and Thermostats',
        'Zone HVAC Equipment Connections',
        'Zone HVAC Forced Air Units',
        'Zone HVAC Radiative/Convective Units',
    }
    assert len(idd_file.uniqueObjects()) == 58
    assert len(idd_file.requiredObjects()) == 2
