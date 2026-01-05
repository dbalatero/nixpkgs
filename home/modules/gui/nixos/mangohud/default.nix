{...}: {
  # MangoHud configuration for gaming performance overlay
  # MangoHud shows FPS, frame times, CPU/GPU usage, temps, etc.

  home.file.".config/MangoHud/MangoHud.conf".text = ''
    # Toggle visibility with Shift_R+F12
    toggle_hud=Shift_R+F12

    # Toggle logging (performance metrics) with Shift_L+F2
    toggle_logging=Shift_L+F2

    # What to display
    fps
    frametime=0
    frame_timing=1

    # GPU stats
    gpu_stats
    gpu_temp
    gpu_core_clock
    gpu_mem_clock
    gpu_power
    gpu_load_change

    # CPU stats
    cpu_stats
    cpu_temp
    cpu_power
    # core_load

    # RAM usage
    ram
    vram

    # Show Wine/Proton version (useful for Steam games)
    wine

    # Show engine version (game engine)
    engine_version

    # Show current resolution
    resolution

    # Position (top-left, top-right, bottom-left, bottom-right, top-center)
    position=top-left

    # Transparency (0-1, where 1 is opaque)
    background_alpha=0.5

    # Font size
    font_size=24

    # Limit FPS display update rate to reduce overhead
    fps_limit_method=late

    # Logging output directory
    output_folder=/home/dbalatero/mangohud-logs

    # Color customization (using hex colors)
    # gpu_color=2e97cb
    # cpu_color=2e9762
    # vram_color=ad64c1
    # ram_color=c26693
    # engine_color=eb5b5b
    # io_color=a491d3
    # frametime_color=00ff00
    # background_color=020202
    # text_color=ffffff

    # Performance tweaks
    gl_vsync=0
  '';
}
