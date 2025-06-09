import numpy as np
import matplotlib.pyplot as plt

# Generate a grass-like noise texture
width, height = 128, 128
red = np.random.randint(40, 80, (height, width))
green = np.random.randint(100, 200, (height, width))
blue = np.random.randint(40, 80, (height, width))

# Stack into RGB image
grass = np.stack((red, green, blue), axis=2).astype(np.uint8)

# Save to file
output_path = 'pygrass_tile.png'
plt.imsave(output_path, grass)


