# %% [markdown]
"""
# example_plot_flowfield

In this example we plot the instantaneous flow-field as a function of position for a fixed depth in a time-step of a TERRA model.

First, we import the objects we require.
"""

import numpy as np
import matplotlib.pyplot as plt
import terratools.terra_model as tm
import terratools.flow_conversion as tf
import glob

# %% [markdown]
"""
Read in the required TERRA model slices (in netCDF format), and convert the flow field from cartesian to a geographical
reference frame.
"""
m = tm.read_netcdf(
    files=glob.glob(
        "/Users/glxjw/mc2/models/muller_bb_visc1/m_bb_044_tvisc1/9-0Ma/NC_037/nc198*.comp"
    )
)
m.add_geog_flow()
# %% [markdown]
"""
Generate latitude and longitude grids at which to evaluate the flow-field.
"""
nlon = 37
lon = np.linspace(-30, 330, nlon)
nlat = 19
lat = np.linspace(-90, 90, nlat)
glon, glat = np.meshgrid(lon, lat, indexing="ij")
flow_velocity = np.empty((3, nlon, nlat))

# %% [markdown]
"""
Loop over the spatial grid at a fixed depth, extracting the flow vector, and scaling to cm/yr.
"""
depth = 100
for i in range(nlon):
    for j in range(nlat):
        flow_velocity[:, i, j] = m.evaluate(lon[i], lat[j], depth, "u_enu", depth=True)
        flow_velocity[:, i, j] = (
            flow_velocity[:, i, j] * (365 * 24 * 60 * 60) * 100
        )  # convert to cm/yr

# %% [markdown]
"""
Finally, plot the flow velocities. The colour scale represents the radial velocity, and the arrows the horizontal velocity. The local
geographic vector is defined as [north,west,radial].
"""
fig, ax = plt.subplots()
max_zvel = np.nanmax(flow_velocity[2, :, :])
psm = ax.pcolor(
    glon, glat, flow_velocity[2, :, :], vmin=-max_zvel, vmax=max_zvel, cmap="seismic"
)
ax.quiver(glon, glat, flow_velocity[0, :, :], flow_velocity[1, :, :])
fig.set_figheight(5)
fig.set_figwidth(10)
fig.colorbar(psm, label="Radial velocity (cm/yr)")
ax.set_xlabel("Longitude ($^\circ$)")
ax.set_ylabel("Latitude ($^\circ$)")
plt.show()
