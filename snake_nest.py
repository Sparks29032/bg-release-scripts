#!/usr/bin/env python

import re
import subprocess

import optparse
import sys
import os

import warnings

def create_option_parser():
    prog_name_short = os.path.basename(sys.argv[0])  # Program name
    
    class Parser(optparse.OptionParser):
        def __init__(self, prog_name, *args, **kwargs):
            super(Parser, self).__init__(*args, **kwargs)
            self.prog_name = prog_name
            
    def detailed_error(self, msg):
        self.exit(2, f"{prog_name}: error: {msg}\n")
    
    parser = Parser(prog_name=prog_name_short,
        usage='\n'.join([
            "python %prog <comma-separated-list-of-python-versions>",
            "For example: python %prog \"3.10, 3.11, 3.12\""
        ]),
        epilog="Please report bugs on https://github.com/Billingegroup/release-scripts/issues."
    )
    parser.add_option(
        '-m',
        '--mamba',
        action="store_true",
        dest="mamba",
        help="""Use mamba instead of conda. Without this option enabled, conda will be used."""
    )
    parser.add_option(
        '-p',
        '--prefix',
        metavar="PREFIX",
        dest="prefix",
        help="""Set the environment name prefix. Environments will be named <prefix><version><suffix>.
The default prefix is \"py-\".""",
    )
    parser.add_option(
        '-s',
        '--suffix',
        metavar="SUFFIX",
        dest="suffix",
        help="""Set the environment name suffix. Environments will be named <prefix><version><suffix>.
The default suffix is \"-env\".""",
    )
    parser.add_option(
        '--vreqs',
        action="store_true",
        dest="vreqs",
        help="""Indicate that the requirements to be installed are version-specific.
This changes the behavior of the inputs for --requirements and --pip-requirements.
Each now takes in an expression of the form \"<prefix>[vsn]<suffix>\".
The program will replace \"[vsn]\" with a version number (e.g. 3.10).
For example, the input \"reqs/py-[vsn]-reqs.txt\" corresponds to files like \"reqs/py-3.10-reqs.txt\"."""
    )
    parser.add_option(
        '-r',
        '--requirements',
        metavar="REQFILE",
        dest="reqs",
        help="""A file containing requirements to install in each environment.
These requirements must be installable through conda/mamba.""",
    )
    parser.add_option(
        '--pip-requirements',
        metavar="PREQFILE",
        dest="pip_reqs",
        help="""A file containing requirements to install in each environment.
These requirements must be installable through pip.
It is recommended to install through conda/mamba unless the packages are available only on PyPi.""",
    )
    parser.add_option(
        '-d',
        '--dev-mode',
        action="store_true",
        dest="dev_mode",
        help="""Install the current directory in developer mode (pip install -e .).
This command will be run in each environment created.""",
    )
    parser.add_option(
        '--nest',
        '--make-snake-nest',
        metavar="NEST-DIR",
        dest="sn_dir",
        help="""Create a snake nest (a directory containing symbolic links to each version-specific Python executable.)
The user should input the path to the desired directory and the program will create that directory if it does not exist.
A warning is thrown if there are existing files in the given directory and no snake nest will be generated.""",
    )

    return parser

if __name__ == "__main__":
    parser = create_option_parser()
    (opts, pargs) = parser.parse_args()
    if len(pargs) != 1:
        parser.error("Improper usage.")
    versions = list(map(str.strip, pargs[0].split(",")))
    
    # Switch environment manager to mamba if chosen
    env_manager = "conda"
    if opts.mamba:
        env_manager = "mamba"

    # Give user-specified names to environments
    prefix = "py-"
    suffix = "-env"
    if opts.prefix is not None:
        prefix = opts.prefix
    if opts.suffix is not None:
        suffix = opts.suffix
    def get_env_name(prefix, suffix, version):
        return prefix + version + suffix
    env_names = list(map(lambda v: get_env_name(prefix, suffix, v), versions))

    # Create environments
    for i, env_name in enumerate(env_names):
        vers_spec_req = opts.reqs
        if opts.vreqs and vers_spec_req is not None:
            vers_spec_req = opts.reqs.replace("[vsn]", versions[i])
        if vers_spec_req is not None:
            subprocess.run(f"{env_manager} create -n {env_name} python={versions[i]} --file={vers_spec_req} --yes", shell=True)
        else:
            subprocess.run(f"{env_manager} create -n {env_name} python={versions[i]} --yes", shell=True)

    # Create snake-nest directory if it does not exist
    sn_dir = opts.sn_dir
    sn_file = os.path.join(sn_dir, "sn_tmp_pyvers.txt")
    if sn_dir is not None:
        if os.path.exists(sn_dir):
            if len(os.listdir(sn_dir)) > 0:
                warnings.warn("Target directory is not empty. No snake nest created.")
                sn_dir = None
            elif not os.path.isdir(sn_dir):
                warnings.warn("Target is not a directory. No snake nest created.")
                sn_dir = None
        else:
            subprocess.run(f"mkdir -p {sn_dir}", shell=True)
    if sn_dir is not None:
        subprocess.run(f"touch {sn_file}", shell=True)

    # Operations to be done within each environment
    in_env_actions = False
    if opts.dev_mode or opts.pip_reqs is not None or sn_dir is not None:
        in_env_actions = True
    if in_env_actions:
        for i, env_name in enumerate(env_names):
            subprocess.run(f"{env_manager} activate {env_name}", shell=True)
            
            # Install pip requirements into each environment
            if opts.pip_reqs is not None or opts.dev_mode:
                vers_spec_preq = opts.pip_reqs
                if opts.vreqs and vers_spec_preq is not None:
                    vers_spec_preq = vers_spec_preq.replace("[vsn]", versions[i])
                if vers_spec_preq is not None:
                    subprocess.run(f"pip install -r {vers_spec_preq} --yes", shell=True)
                if opts.dev_mode:
                    subprocess.run(f"pip install -e . --yes", shell=True)
            
            # Setup the snake nest
            if sn_dir is not None:
                subprocess.run(f"which python >> {sn_file}", shell=True)
        
            subprocess.run(f"{env_manager} deactivate", shell=True)
            
    # Setup symbolic links in snake nest
    if sn_dir is not None:
        with open(sn_file, 'r') as snf:
            for i, sym_link in enumerate(snf):
                sym_link = os.path.abspath(sym_link).strip()
                sym_name = os.path.join(sn_dir, f"python-{versions[i]}").strip()
                subprocess.run(f"ln -s {sym_link} {sym_name}", shell=True)
        subprocess.run(f"rm {sn_file}", shell=True)
            
