import numpy as np
import shutil
from subprocess import Popen, PIPE, STDOUT
import os
import glob
import pkgutil
from copy import deepcopy


def make_build_files(project_name, molar_composition,
                     pressure_bounds, temperature_bounds,
                     endmember_file, solution_file,
                     option_file,
                     solutions, excludes):
    """
    This function makes a collection of PerpleX build files
    (which are the input files used by other PerpleX programs).

    The benefit of this function over build is that it
    (a) specifically considers only input files for 2D Gibbs
    minimization, and (b) can split a P-T domain into an arbitrary
    number of chunks, defined by P and T dividing lines. This
    removes some problems with memory limits when trying to create
    phase diagrams over all P and T space.

    Parameters
    ----------
    project_name: string
        A string used to define the project directory and
        build file names.

    molar_composition: dictionary
        A dictionary containing the molar amounts of the
        components in the thermodynamic data files
        (often MGO, FEO etc...). Sometimes the datafiles
        have components in mixed case (MgO, FeO etc).

    pressure_bounds: list of floats
        A list of pressures that partition the build files.
        Should be of at least length two
        (minimum and maximum pressure).

    temperature_bounds: list of floats
        A list of temperatures that partition the build files.
        Should be of at least length two
        (minimum and maximum temperature).

    endmember_file: string
        Path to the endmember thermodynamic data file
        (usually *ver.dat)

    solution_file: string
        Path to the solution file (usually ?_solution_model.dat)

    option_file: string
        Path to the PerpleX option file (usually perplex_option.dat).

    solutions: list of strings
        List of solutions to be considered in the minimization

    excludes: list of strings
        List of endmembers excluded in the minimization
    """

    # Create project directory
    if os.path.exists(project_name):
        raise Exception(f'\nA folder called {project_name} already exists! \n'
                        'Please select another name or delete this folder.')
    else:
        os.makedirs(project_name)
        for filename in [endmember_file, solution_file, option_file]:
            shutil.copy2(filename, project_name)

    # Read in template

    template = pkgutil.get_data('terratools',
                                'properties/data/perplex_build_template.txt')
    template = template.decode('ascii')
    template = template.replace('[X-ENDMEMBER_FILE-X]', endmember_file)
    template = template.replace('[X-SOLUTION_FILE-X]', solution_file)
    template = template.replace('[X-OPTION-X]', option_file)

    c_string = ''
    for c, v in molar_composition.items():
        c_string += f'{c:7s}    1    {v}        '
        c_string += '0.00000      0.00000     molar amount\n'

    template = template.replace('[X-COMPONENTS-X]\n', c_string)

    sol_string = ''
    for ph in solutions:
        sol_string += f'{ph}\n'

    template = template.replace('[X-SOLUTIONS-X]\n', sol_string)

    exclude_string = ''
    for ph in excludes:
        exclude_string += f'{ph}\n'

    template = template.replace('[X-EXCLUDED_PHASES-X]\n', exclude_string)

    for iP in range(len(pressure_bounds) - 1):
        for iT in range(len(temperature_bounds) - 1):

            basename = f'{project_name}_{iP:02d}_{iT:02d}'

            LP_bar = str(pressure_bounds[iP]/1.e5)
            HP_bar = str(pressure_bounds[iP+1]/1.e5)
            output = deepcopy(template)

            output = output.replace('[X-NAME-X]', basename)
            output = output.replace('[X-LP-X]', LP_bar)
            output = output.replace('[X-HP-X]', HP_bar)
            output = output.replace('[X-LT-X]', str(temperature_bounds[iT]))
            output = output.replace('[X-HT-X]', str(temperature_bounds[iT+1]))

            with open(f'{project_name}/{basename}.dat', 'w') as outfile:
                outfile.write(output)

    return True


def run_build_files(path_to_project, path_to_perplex):
    """
    Runs PerpleX-vertex (Gibbs minimization)
    and PerpleX-pssect (postscript plotting) on the
    collection of build files created by
    the make_build_files function.

    Parameters
    ----------
    path_to_project: string
        The path to the project defined by the
        project_name parameter in make_build_files.

    path_to_perplex: string
        The path to the directory containing the
        PerpleX executables (vertex and pssect).
    """
    working_directory = os.getcwd()
    os.chdir(path_to_project)
    project_name = os.path.basename(os.getcwd())

    roots = []
    for file in os.listdir(os.getcwd()):
        if file.startswith(f"{project_name}_"):
            roots.append(file.replace('.dat', ''))

    n_files = len(roots)
    for i, root in enumerate(roots):
        print(f'    running vertex ({i+1}/{n_files})...')
        stdin = f'{root}\n0\n'
        p = Popen(f'{path_to_perplex}/vertex', stdout=PIPE, stdin=PIPE,
                  stderr=STDOUT, encoding='utf8')
        stdout = p.communicate(input=stdin)[0]
        print(stdout)

        print('    running pssect...')
        stdin = f'{root}\nn\n'
        pssect = f'{path_to_perplex}/pssect'
        p = Popen(pssect, stdout=PIPE, stdin=PIPE,
                  stderr=STDOUT, encoding='utf8')
        stdout = p.communicate(input=stdin)[0]
        print(stdout)

    os.chdir(working_directory)


def perplex_to_grid(path_to_project,
                    pressure_bounds,
                    temperature_bounds,
                    pressures,
                    temperatures,
                    path_to_perplex):
    """
    Runs PerpleX-werami on the files created by
    run_build_files. Returns a 3D numpy array
    where out[i,j,k] is property k at
    the ith pressure and jth temperature.
    The properties k are pressure, temperature
    (both duplicated as a formatting check),
    density, Vp and Vs.

    Attempts are made to fill NaN elements
    (from vertex / werami failures) by running werami
    on individual points, taking a 3x3 block mean,
    and by linear extrapolation in the lowest
    pressure row.

    Parameters
    ----------
    path_to_project: string
        The path to the project defined by the
        project_name parameter in make_build_files.

    pressure_bounds: list of floats
        A list of pressures that partition the build files.
        Should be of at least length two
        (minimum and maximum pressure).

    temperature_bounds: list of floats
        A list of temperatures that partition the build files.
        Should be of at least length two
        (minimum and maximum temperature).

    pressures: numpy array
        Equally spaced pressures defining the
        property grid. Most easily created using
        numpy.linspace().

    temperatures: numpy array
        Equally spaced temperatures defining the
        property grid. Most easily created using
        numpy.linspace().

    path_to_perplex: string
        The path to the directory containing the
        PerpleX executables (vertex and pssect).

    Returns
    -------
    out: 3D numpy array
        An array of thermodynamic properties.
        out[i,j,k] is property k at
        the ith pressure and jth temperature.
        The properties k are pressure, temperature
        (both duplicated as a formatting check),
        density, Vp and Vs.
    """

    working_directory = os.getcwd()
    os.chdir(path_to_project)
    project_name = os.path.basename(os.getcwd())

    nP = len(pressures)
    nT = len(temperatures)
    pp, TT = np.meshgrid(pressures, temperatures)
    out = np.empty((nT, nP, 5))
    out[:, :, 0] = pp
    out[:, :, 1] = TT

    for iP in range(len(pressure_bounds) - 1):
        for iT in range(len(temperature_bounds) - 1):
            minP, maxP = pressure_bounds[iP], pressure_bounds[iP+1]
            minT, maxT = temperature_bounds[iT], temperature_bounds[iT+1]

            Pidx = np.argwhere(np.all([pressures >= minP,
                                       pressures < maxP], axis=0)).T[0]
            Tidx = np.argwhere(np.all([temperatures >= minT,
                                       temperatures < maxT], axis=0)).T[0]

            Ps = pressures[Pidx]
            Ts = temperatures[Tidx]

            basename = f'{project_name}_{iP:02d}_{iT:02d}'
            print('    removing existing tabbed files from same build file...')
            fileList = glob.glob(f'./{basename}_?.tab')
            for filePath in fileList:
                os.remove(filePath)

            print('    running werami...')
            stdin = f'{basename}\n2\n2\nn\n13\nn\n14\nn\n0\ny\n'
            stdin += f'{Ps[0]/1.e5} {Ps[-1]/1.e5}\n{Ts[0]} {Ts[-1]}\n'
            stdin += f'{len(Ps)} {len(Ts)}\n0\n'
            werami = f'{path_to_perplex}/werami'
            p = Popen(werami, stdout=PIPE, stdin=PIPE,
                      stderr=STDOUT, encoding='utf8')
            stdout = p.communicate(input=stdin)[0]

            print('    loading data into table...')
            data = np.loadtxt(f'{basename}_1.tab', skiprows=13)

            # Try to fill nans with werami
            nanidx = np.unique(np.argwhere(np.isnan(data))[:, 0])

            for idx in nanidx:
                P, T = data[idx, :2]
                P = max(P/100000., 1.e-10)
                stdin = f'{basename}\n1\n{P} {T}\n99 99\n0\n'
                p = Popen(werami, stdout=PIPE, stdin=PIPE,
                          stderr=STDOUT, encoding='utf8')
                stdout = p.communicate(input=stdin)[0]
                prps = stdout.split('Seismic Properties:')[1]
                prps = prps.split('System')[1].split('\n')[0].split()
                Vp, Vs = prps[4:6]
                if Vp != 'NaN':
                    data[idx, 3] = float(Vp)
                if Vs != 'NaN':
                    data[idx, 4] = float(Vs)

            data = data.reshape(len(Ts), len(Ps), 5)

            out[Tidx[0]:Tidx[-1]+1, Pidx[0]:Pidx[-1]+1, 2:] = data[:, :, 2:]

    # Make pressure the first axis
    out = np.swapaxes(out, 0, 1)

    # check all nans are filled
    nan_indices = np.unique(np.argwhere(np.isnan(out))[:, 0])

    if len(nan_indices) > 0:
        print('The program werami has not been able to replace all nans.')
        print('Using cell interpolation on remaining cells.')

        nan_cells = np.unique(np.argwhere(np.isnan(out))[:, :2], axis=0)

        for i_cell, j_cell in nan_cells:

            for i_prp in [2, 3, 4]:
                block = out[i_cell-1:i_cell+2, j_cell-1:j_cell+2, i_prp]
                if block.shape[0] > 0:
                    if block.shape[1] > 0:
                        out[i_cell, j_cell, i_prp] = np.nanmean(block)

    nan_indices = np.unique(np.argwhere(np.isnan(out))[:, 0])
    if len(nan_indices) > 0:
        nan_cells = np.unique(np.argwhere(np.isnan(out))[:, :2], axis=0)
        for (i, j) in nan_cells:
            if i == 0:
                out[i, j, 3:] = 2.*out[i+1, j, 3:] - out[i+2, j, 3:]

    nan_indices = np.unique(np.argwhere(np.isnan(out))[:, 0])
    if len(nan_indices) > 0:
        print('The following data with nans could not be filled:')
        nan_cells = np.unique(np.argwhere(np.isnan(out))[:, :2], axis=0)
        for (i, j) in nan_cells:
            print(out[i, j])

    os.chdir(working_directory)

    return out
