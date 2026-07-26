# optional — guard if library/hardware missing
try:
    from rpi_ws281x import PixelStrip, Color
    _strip = PixelStrip(9, 18, 800000, 10, False, 64, 0)
    _strip.begin()
    def pixels_rgb(r, g, b):
        c = Color(r, g, b)
        for i in range(_strip.numPixels()):
            _strip.setPixelColor(i, c)
        _strip.show()
except Exception:
    def pixels_rgb(r, g, b):
        pass



#   On note on/off, call pixels_rgb(...) next to set_backlight(...). On shutdown:
#   pixels_rgb(0, 0, 0)
#
#   Use GPIO 18  
