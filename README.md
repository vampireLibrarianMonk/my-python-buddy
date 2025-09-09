# Environment Setup

## Conda Environment
conda create -n my-python-buddy -c conda-forge -y python=3.10 pip django=5
conda activate my-python-buddy

### Save environment file
conda env export --no-builds | grep -v "^prefix: " > environment.yml

