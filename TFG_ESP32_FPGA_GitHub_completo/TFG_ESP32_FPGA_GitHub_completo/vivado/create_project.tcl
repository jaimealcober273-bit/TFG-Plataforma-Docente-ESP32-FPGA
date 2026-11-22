# Ejecutar: vivado -mode batch -source vivado/create_project.tcl
# Crea un proyecto nuevo a partir de los archivos versionados.
set repo_root [file normalize [file join [file dirname [info script]] ..]]
set out_dir [file join $repo_root vivado build]
create_project project_TFG $out_dir -part xc7a100tcsg324-1 -force
set_property target_language Verilog [current_project]

add_files -fileset sources_1 [file join $repo_root fpga rtl top.v]
set_property top top [get_filesets sources_1]

add_files -fileset constrs_1 [file join $repo_root fpga constraints esp32_TFG.xdc]

add_files -fileset sim_1 [file join $repo_root fpga sim tb_top.v]
set_property top tb_top [get_filesets sim_1]

update_compile_order -fileset sources_1
update_compile_order -fileset sim_1
puts "Proyecto creado en $out_dir"
