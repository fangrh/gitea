"""Test snakemake build in the builder container."""
import subprocess, tempfile, pathlib, os, shutil

tmp = tempfile.mkdtemp(prefix='smktest-')
result = subprocess.run(
    ['git', '--git-dir', '/data/git/repositories/ruihuanfang/phononic-superconductor.git',
     'archive', 'main'],
    capture_output=True
)
subprocess.run(['tar', '-x', '-C', tmp], input=result.stdout)

snakefile = pathlib.Path(tmp) / 'Snakefile'
print('Snakefile:', snakefile, snakefile.exists())

import gdsfactory as gf
gf.gpdk.PDK.activate()

import snakemake
try:
    snakemake.snakemake(
        snakefile=str(snakefile),
        targets=['build_gds'],
        config={'design': 'example_mzi'},
        cores=1,
        printshellcmds=True,
    )
    print('Snakemake OK')
except Exception as e:
    print('Snakemake error:', type(e).__name__, e)

for gds in sorted(pathlib.Path(tmp).rglob('*.gds')):
    print('GDS:', gds.relative_to(tmp))

shutil.rmtree(tmp, ignore_errors=True)
print('Done')
