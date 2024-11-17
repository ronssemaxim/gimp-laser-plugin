#!/usr/bin/env python2

from gimpfu import *
import gtk

import math
from array import *

gettext.install("gimp20-python", gimp.locale_directory, unicode=True)

def laser_power(min_val, max_val, pixel, threshold):
  """
  Calculate value of the laser output based on:
  min_val: (int) minimum value to use, even while moving the head
  max_val: (int) maximum value to use, meaning where the darkest area will be
  pixel: brightness of the current pixel
  threshold: skip the pixel if it is lower than the threshold
  """
  if 255 - pixel < threshold: 
    return 0
  return min_val + (max_val - min_val) * (255 - pixel) / 255


def image_to_gcode(timg, drawable, mcode, outWidth, pixSize, feedRate,
                   minPower, maxPower, threshold) :
  
  dlg = gtk.FileChooserDialog("Pick a file", None,
                              gtk.FILE_CHOOSER_ACTION_SAVE,
                              (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, gtk.STOCK_OK, gtk.RESPONSE_OK))
  dlg.set_do_overwrite_confirmation(True)
  ok = dlg.run()
  filename = dlg.get_filename()
  dlg.destroy()  
  
  width = int(outWidth / pixSize)
  height = int(timg.height * width / timg.width)

  timg = pdb.gimp_image_duplicate(timg)
  pdb.gimp_image_scale(timg, width, height)

  # Flatten image so that we handle alpha channel correctly
  pdb.gimp_context_push()
  pdb.gimp_context_set_background((255, 255, 255))
  pdb.gimp_image_flatten(timg)
  pdb.gimp_context_pop()

  if pdb.gimp_image_base_type(timg) != GRAY:
      pdb.gimp_image_convert_grayscale(timg)

  drawable = pdb.gimp_image_get_active_drawable(timg)
  pixels = drawable.get_pixel_rgn(0, 0, width, height)
  pixels = array('B', pixels[0:width, 0:height])

  pdb.gimp_progress_init('Generating GCode...', None)

  with open(filename, 'w+') as f:
    f.write('G21G90\nM%dF%d\n' % (int(mcode)+3, feedRate))
    # todo: test this, possible fix for random black line when starting
    # f.write('G1X0Y0S0\n')

    forward = True

    for row in range(height):
      y = row
      lastPower = None

      pdb.gimp_progress_update(float(row) / height)

      # save all values we will print for this row
      row_vals = []
      for col in range(width):
        x = col if forward else (width - col - 1)
        pixel = pixels[width * y + x]
        power = laser_power(minPower, maxPower, pixel, threshold)
        end = col == width - 1


        if not end and col and power != lastPower or end:
          # add to values to add
          row_vals.append({"x": x, "power": lastPower})

        lastPower = power

      
      # skip row if its only 0
      if sum([item["power"] for item in row_vals]) == 0:
        continue

      # only now do we swap the direction, in case the rows are empty we dont need to swap
      forward = not forward
      
      # when going backwards, skip the rest (last in order) of the line if it is empty
      if len(row_vals) > 1 and not forward and row_vals[-1]["power"] == 0:
        row_vals[-1]["x"] = row_vals[-2]["x"] + pixSize
      # same for forwards: skip the beginning of the line if it is empty
      if len(row_vals) > 1 and forward and row_vals[0]["power"] == 0:
        row_vals[0]["x"] = row_vals[1]["x"] - pixSize

      [f.write('G1X%0.2fY%0.2fS%d\n' % (item["x"] * pixSize, y * pixSize, item["power"])) for item in row_vals]


    f.write('M5S0\n')

    pdb.gimp_image_delete(timg)
    pdb.gimp_progress_end()


register(
  'BUILDBOTICS-laser-plugin',
  N_('Laser engraving by Maxim Ronsse'),
  'Export image to g-code for laser engraving',
  'Maxim Ronsse',
  'Maxim Ronsse',
  '2024',
  N_('Export g-code for laser engraving...'),
  '*',
  [
    (PF_IMAGE, "timg",       "Input image", None),
    (PF_DRAWABLE, "drawable", "Input drawable", None),
    (PF_BOOL,  'mcode',  'Use M4', False),
    (PF_FLOAT,  'outWidth',  'Output image width (mm)', 100),
    (PF_FLOAT,  'pixSize',   'Size of one output pixel (mm)', 0.25),
    (PF_FLOAT,  'feedRate',  'Feed rate in mm/minute', 900),
    (PF_INT,    'minPower',  'Mimimum LASER S-value', 2),
    (PF_INT,    'maxPower',  'Maximum LASER S-value', 50),
    (PF_INT,    'threshold', 'Minimum pixel value', 20),
  ],
  [],
  image_to_gcode,
  menu="<Image>/File/Export",
  domain=("gimp20-python", gimp.locale_directory)
  )

main()
