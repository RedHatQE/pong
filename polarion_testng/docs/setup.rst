.. setup::

Getting pong setup
==================

Getting pong setup is a 2 stage affair.  The first step is to install the dependencies, and the second step is to
make sure configuration files are in place.  I recommend installing a virtualenv and cloning pong to it::

    mkdir -p venvs
    virtualenv venvs/pong
    source venvs/pong/bin/activate
    git clone https://github.com/RedHatQE/polarion-testng.git
    pushd polarion_testng
    pip install -r requirements.txt

You will also need to git clone and install the pylarion project.