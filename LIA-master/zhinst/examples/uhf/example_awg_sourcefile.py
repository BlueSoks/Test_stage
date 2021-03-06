# -*- coding: utf-8 -*-
"""
Zurich Instruments LabOne Python API Example

Demonstrate how to connect to a Zurich Instruments Arbitrary Waveform Generator
and compile/upload an AWG program to the instrument.
"""

# Copyright 2017 Zurich Instruments AG

from __future__ import print_function
import time
import os
import zhinst.utils

# Only used if this example is ran without the awg_sourcefile parameter: To
# ensure that we have a .seqc source file to use in this example, we write this
# to disk and then compile this file.
source = """// Define an integer constant
const N = 4096;
// Create two Gaussian pulses with length N points,
// amplitude +1.0 (-1.0), center at N/2, and a width of N/8
wave gauss_pos = 1.0*gauss(N, N/2, N/8);
wave gauss_neg = -1.0*gauss(N, N/2, N/8);
// Continuous playback.
while (true) {
  // Play pulse on AWG channel 1
  playWave(gauss_pos);
  // Wait until waveform playback has ended
  waitWave();
  // Play pulses simultaneously on both AWG channels
  playWave(gauss_pos, gauss_neg);
}"""


def run_example(device_id, awg_sourcefile=None):
    """
    Connect to a Zurich Instruments UHF Lock-in Amplifier or UHFAWG, compile,
    upload and run an AWG sequence program.

    Requirements:

      UHFAWG or UHFLI with UHF-AWG Arbitrary Waveform Generator Option.

    Arguments:

      device_id (str): The ID of the device to run the example with. For
        example, `dev2006` or `uhf-dev2006`.

      awg_sourcefile (str, optional): Specify an AWG sequencer file to compile
        and upload. This file must exist in the AWG source sub-folder of your
        LabOne data directory (this location is provided by the
        awgModule/directory parameter). The source folder must not be included;
        specify the filename only with extension.

    Raises:

      Exception: AWG functionality is not available.

      RuntimeError: If the device is not "discoverable" from the API.

    See the "LabOne Programing Manual" for further help, available:
      - On Windows via the Start-Menu:
        Programs -> Zurich Instruments -> Documentation
      - On Linux in the LabOne .tar.gz archive in the "Documentation"
        sub-folder.
    """

    # Settings
    apilevel_example = 6  # The API level supported by this example.
    err_msg = "This example can only be ran on either a UHFAWG or a UHF with the AWG option enabled."
    # Call a zhinst utility function that returns:
    # - an API session `daq` in order to communicate with devices via the data server.
    # - the device ID string that specifies the device branch in the server's node hierarchy.
    # - the device's discovery properties.
    (daq, device, props) = zhinst.utils.create_api_session(device_id, apilevel_example, required_devtype='UHF',
                                                           required_options=['AWG'], required_err_msg=err_msg)
    zhinst.utils.api_server_version_check(daq)

    # Create a base instrument configuration: disable all outputs, demods and scopes.
    general_setting = [['/%s/demods/*/enable' % device, 0],
                       ['/%s/demods/*/trigger' % device, 0],
                       ['/%s/sigouts/*/enables/*' % device, 0],
                       ['/%s/scopes/*/enable' % device, 0]]
    if 'IA' in props['options']:
        general_setting.append(['/%s/imps/*/enable' % device, 0])
    daq.set(general_setting)
    # Perform a global synchronisation between the device and the data server:
    # Ensure that the settings have taken effect on the device before continuing.
    daq.sync()

    print("Disabling AWG.")
    daq.setInt('/' + device + '/awgs/0/enable', 1)
    daq.sync()

    # Create an instance of the AWG Module
    awgModule = daq.awgModule()
    awgModule.set('awgModule/device', device)
    awgModule.execute()

    # Get the LabOne user data directory.
    data_dir = awgModule.getString('awgModule/directory')
    # The AWG Tab in the LabOne UI also uses this directory for AWG segc files.
    src_dir = os.path.join(data_dir, "awg", "src")
    if not os.path.isdir(src_dir):
        # The data directory is created by the AWG module and should always exist. If this exception is raised,
        # something might be wrong with the file system.
        raise Exception("AWG module wave directory {} does not exist or is not a directory".format(src_dir))

    # Note, the AWG source file must be located in the AWG source directory of the user's LabOne data directory.
    if awg_sourcefile is None:
        # Write an AWG source file to disk that we can compile in this example.
        awg_sourcefile = "ziPython_example_awg_sourcefile.seqc"
        with open(os.path.join(src_dir, awg_sourcefile), "w") as f:
            f.write(source)
    else:
        if not os.path.exists(os.path.join(src_dir, awg_sourcefile)):
            raise Exception("The file {} does not exist, this must be specified via an "
                            "absolute or relative path.".format(awg_sourcefile))

    print("Will compile and load", awg_sourcefile, "from", src_dir)

    # Transfer the AWG sequence program. Compilation starts automatically.
    awgModule.set('awgModule/compiler/sourcefile', awg_sourcefile)
    # Note: when using an AWG program from a source file (and only then), the compiler needs to
    # be started explicitly:
    awgModule.set('awgModule/compiler/start', 1)
    timeout = 20
    t0 = time.time()
    while awgModule.get('awgModule/compiler/status')['compiler']['status'][0] == -1:
        time.sleep(0.1)
        if time.time() - t0 > timeout:
            Exception("Timeout")

    if awgModule.get('awgModule/compiler/status')['compiler']['status'][0] == 1:
        # compilation failed, raise an exception
        raise Exception(awgModule.get('awgModule/compiler/statusstring')['compiler']['statusstring'][0])
    else:
        if awgModule.get('awgModule/compiler/status')['compiler']['status'][0] == 0:
            print("Compilation successful with no warnings, will upload the program to the instrument.")
        if awgModule.get('awgModule/compiler/status')['compiler']['status'][0] == 2:
            print("Compilation successful with warnings, will upload the program to the instrument.")
            print("Compiler warning: " +
                  awgModule.get('awgModule/compiler/statusstring')['compilelsr']['statusstring'][0])
        # Wait for the waveform upload to finish
        time.sleep(0.2)
        i = 0
        while awgModule.get('awgModule/progress')['progress'][0] < 1.0:
            print("{} progress: {}".format(i, awgModule.get('awgModule/progress')['progress'][0]))
            time.sleep(0.5)
            i += 1

    print('Success. Enabling the AWG.')
    daq.setInt('/' + device + '/awgs/0/enable', 1)
