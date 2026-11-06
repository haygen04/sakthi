-- ============================================================================
-- Seed Data for Dimensions and PMS Source Simulation
-- ============================================================================

-- Shops
INSERT INTO dim_shop (shop_code, shop_name, manager_name) VALUES
('FOUNDRY', 'Automotive Casting Foundry Division', 'R. Balasubramanian'),
('MACHINE_SHOP', 'Precision Machining & CNC Division', 'K. Senthil Kumar')
ON DUPLICATE KEY UPDATE shop_name = VALUES(shop_name);

-- Shifts
INSERT INTO dim_shift (shift_code, shift_name, start_time, end_time, hours) VALUES
('SHIFT_A', 'Morning Shift', '06:00:00', '14:00:00', 8.00),
('SHIFT_B', 'Afternoon Shift', '14:00:00', '22:00:00', 8.00),
('SHIFT_C', 'Night Shift', '22:00:00', '06:00:00', 8.00)
ON DUPLICATE KEY UPDATE shift_name = VALUES(shift_name);

-- Parts
INSERT INTO dim_part (part_number, part_name, shop_code, material_grade, unit_weight_kg, standard_cost, is_critical) VALUES
('P-BRK-DISC-01', 'Ventilated Brake Disc Rotor 280mm', 'FOUNDRY', 'Grey Iron FG 260', 7.450, 185.00, TRUE),
('P-BRK-DRUM-02', 'Heavy Duty Brake Drum 220mm', 'FOUNDRY', 'Grey Iron FG 260', 9.800, 240.00, TRUE),
('P-STR-KNCK-03', 'Steering Knuckle Front LH', 'FOUNDRY', 'Ductile Iron SGI 500/7', 5.600, 310.00, TRUE),
('P-STR-KNCK-04', 'Steering Knuckle Front RH', 'FOUNDRY', 'Ductile Iron SGI 500/7', 5.600, 310.00, TRUE),
('P-FLW-WHL-05', 'Engine Flywheel Dual Mass 240mm', 'FOUNDRY', 'Grey Iron FG 300', 11.200, 420.00, FALSE),
('M-BRK-DISC-01', 'Machined Brake Disc Finished', 'MACHINE_SHOP', 'FG 260 Precision', 6.950, 295.00, TRUE),
('M-BRK-DRUM-02', 'Machined Brake Drum Finished', 'MACHINE_SHOP', 'FG 260 Precision', 9.100, 360.00, TRUE),
('M-STR-KNCK-03', 'Machined Steering Knuckle LH', 'MACHINE_SHOP', 'SGI 500/7 Precision', 5.150, 480.00, TRUE),
('M-STR-KNCK-04', 'Machined Steering Knuckle RH', 'MACHINE_SHOP', 'SGI 500/7 Precision', 5.150, 480.00, TRUE),
('M-FLW-WHL-05', 'Machined Balanced Flywheel', 'MACHINE_SHOP', 'FG 300 Dynamic', 10.400, 620.00, FALSE)
ON DUPLICATE KEY UPDATE part_name = VALUES(part_name);

-- Machines
INSERT INTO dim_machine (machine_code, machine_name, shop_code, line_name, rated_capacity_per_hour) VALUES
('FND-DISA-01', 'Disamatic High Pressure Molding Line 1', 'FOUNDRY', 'Molding Line 1', 120),
('FND-DISA-02', 'Disamatic High Pressure Molding Line 2', 'FOUNDRY', 'Molding Line 2', 120),
('FND-POUR-01', 'Auto Pouring Unit Inductotherm 1', 'FOUNDRY', 'Pouring Line 1', 150),
('MC-CNC-01', 'Doosan Twin Spindle CNC 01', 'MACHINE_SHOP', 'Rotor Line A', 45),
('MC-CNC-02', 'Doosan Twin Spindle CNC 02', 'MACHINE_SHOP', 'Rotor Line A', 45),
('MC-CNC-03', 'Doosan Twin Spindle CNC 03', 'MACHINE_SHOP', 'Rotor Line B', 45),
('MC-VMC-01', 'Makino High Speed VMC 01', 'MACHINE_SHOP', 'Knuckle Line', 30),
('MC-VMC-02', 'Makino High Speed VMC 02', 'MACHINE_SHOP', 'Knuckle Line', 30),
('MC-BAL-01', 'Schenck Dynamic Balancing Line 01', 'MACHINE_SHOP', 'Finishing Line', 60)
ON DUPLICATE KEY UPDATE machine_name = VALUES(machine_name);

-- Defect Codes
INSERT INTO dim_defect (defect_code, defect_name, shop_code, category, severity) VALUES
('DEF-SAND-INC', 'Sand Inclusion / Mold Erosion', 'FOUNDRY', 'MOLDING', 'MAJOR'),
('DEF-POROSITY', 'Gas Porosity / Pin Holes', 'FOUNDRY', 'METALLURGICAL', 'CRITICAL'),
('DEF-SHRINKAGE', 'Shrinkage Cavity / Porosity', 'FOUNDRY', 'METALLURGICAL', 'CRITICAL'),
('DEF-COLD-SHUT', 'Cold Shut / Incomplete Pour', 'FOUNDRY', 'POURING', 'MAJOR'),
('DEF-SLAG', 'Slag / Dross Inclusion', 'FOUNDRY', 'POURING', 'MAJOR'),
('DEF-CORE-SHIFT', 'Core Shift / Wall Thinning', 'FOUNDRY', 'CORE_MAKING', 'MAJOR'),
('DEF-FLASH', 'Heavy Metal Flash / Fin', 'FOUNDRY', 'MOLDING', 'MINOR'),
('DEF-DIM-OOT', 'Dimensional Out of Tolerance', 'MACHINE_SHOP', 'MACHINING', 'CRITICAL'),
('DEF-SURF-CHAT', 'Surface Roughness / Chatter Marks', 'MACHINE_SHOP', 'TOOLING', 'MAJOR'),
('DEF-TOOL-BRK', 'Drill / Tap Breakage inside part', 'MACHINE_SHOP', 'TOOLING', 'CRITICAL'),
('DEF-RUNOUT', 'Face Runout / Dynamic Wobble', 'MACHINE_SHOP', 'MACHINING', 'MAJOR'),
('DEF-SUB-POR', 'Subsurface Casting Porosity revealed', 'MACHINE_SHOP', 'RAW_MATERIAL', 'MAJOR'),
('DEF-BURR', 'Heavy Burr / Incomplete Chamfer', 'MACHINE_SHOP', 'DEBURRING', 'MINOR')
ON DUPLICATE KEY UPDATE defect_name = VALUES(defect_name);

