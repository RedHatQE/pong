from subprocess import Popen, STDOUT
import os


def clone_hy(dest):
    owd = os.getcwd()
    os.chdir(dest)
    cmd = "git clone https://github.com/hylang/hy.git"
    proc = Popen(cmd, stdout=STDOUT, stderr=STDOUT)
    outp, _ = proc.communicate()
    print outp
    if proc.returncode != 0:
        raise Exception("Unable to clone hy")
    os.chdir(owd)


def is_hy_installed():
    try:
        import hy
        return True
    except ImportError:
        return False


def install_hy(hypath):
    owd = os.getcwd()
    try:
        if not is_hy_installed():
            hypath_dir = os.path.dirname(hypath)
            if not hypath_dir:
                hypath_dir = "."
            clone_hy(hypath_dir)
            os.chdir(hypath)
            proc = Popen("python setup.py install", stdout=STDOUT, stderr=STDOUT)
            print proc.communicate()[0]
        else:
            return
    except:
        pass
    finally:
        os.chdir(owd)

if __name__ == "__main__":
    install_hy("/tmp/hy")