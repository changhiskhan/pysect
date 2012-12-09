"""
Make git bisect run a little easier so you don't have to
mess with the environment and also make a custom shell script
additionally it suppresses output during build
"""
import os
import subprocess
from subprocess import PIPE

def _git_command(repo_path):
    return ('git --git-dir=%s/.git --work-tree=%s' % (repo_path, repo_path))

class BisectRepo(object):
    """
    Manage git bisecting information
    """
    def __init__(self, repo_path, test_command, build_command=None,
                 build_args=None, tmp_dir='~/tmp'):
        self.repo_path = repo_path
        self.git = _git_command(self.repo_path)
        self.build = build_command
        self.test = os.path.expanduser(test_command)
        self.build_args = [] if build_args is None else build_args
        self.tmp_dir = os.path.expanduser(tmp_dir)

    def start(self, bad=None, good=None):
        return self._git('bisect', 'start', bad, good)

    def run_build_step(self):
        if self.build is not None:
            child = self._exec(self.build, *self.build_args, cwd=self.repo_path,
                              redirect=True)
            (out, err) = child.communicate()
            if child.returncode != 0:
                print out
                cmd = ' '.join(self.build_args + [self.build])
                raise subprocess.CalledProcessError(child.returncode, cmd)
            return out, err

    def checkout(self, commit):
        status = self._git('checkout', commit)
        return status

    def bad(self):
        status = self._git('bisect', 'bad')
        return status

    def good(self):
        status = self._git('bisect', 'good')
        return status

    def _git(self, *args, **kwargs):
        cmd = self.git
        if 'cwd' not in kwargs:
            kwargs['cwd'] = self.repo_path

        args = list(args)
        cmd = ' '.join([cmd] + args)
        rs = self._exec(cmd, **kwargs)
        if rs is not None:
            return rs.communicate()

    def _exec(self, cmd, *args, **kwargs):
        redirect = kwargs.pop('redirect', False)
        shell = kwargs.pop('shell', True)
        args = list(args)
        args.insert(0, cmd)
        if redirect:
            #print 'Calling %s' % ' '.join(args)
            p = subprocess.Popen(args, stdout=PIPE, stderr=PIPE, stdin=PIPE,
                                 shell=shell, env=os.environ.copy(), **kwargs)
            p.wait()
            return p
        else:
            exec_type = kwargs.pop('exec_type', 'call')
            f = getattr(subprocess, exec_type)
            #print 'Calling %s' % ' '.join(args)
            p = f(' '.join(args), shell=shell,
                  env=os.environ.copy(), **kwargs)

    def run(self, bad, good):
        """
        Run until we see "* is the first bad commit"
        """
        self.start(bad, good)
        done = False
        try:
            while not done:
                done = self._step()
        finally:
            print 'Resetting'
            self._git('bisect', 'reset')
            print 'Rebuilding head'
            self.run_build_step()

    def _step(self):
        """
        Build, test, mark
        """
        try:
            print 'Building'

            self.run_build_step()

            print 'Build completed'
            (stdout, stderr) = self._exec('python %s' % self.test,
                                          redirect=True).communicate()

            if 'AssertionError' in stderr:
               (stdout, stderr) = self._git('bisect', 'bad', redirect=True)
            else:
               (stdout, stderr) = self._git('bisect', 'good', redirect=True)

            print stdout
            if 'is the first bad commit' in stdout:
                return  True
        except subprocess.CalledProcessError:
            print 'Skipping'
            self._git('bisect', 'skip')
        return False

def run(test, bad, good, repo_path='.', build=None,
        build_args=None):
    repo = BisectRepo(repo_path, test, build_command=build,
                      build_args=build_args)
    status = repo.run(bad, good)
    return status

def print_usage():
    help_str = """
pysect <good> <test_script> [<repo_oath>] [<bad>] [<build>]\n
<repo_path> defaults to ~/code/pandas'
<bad> defaults to HEAD
<build> defaults to 'make tseries'
"""

if __name__ == '__main__':
    import sys

    args = sys.argv[1:]
    good = 'v0.9.1'
    path = os.path.expanduser('~/code/pandas')
    test = '~/code/pysect/pysect/__test__.py'
    bad = 'HEAD'
    build = 'python setup.py build_ext --inplace'
    build_args = []

    if len(args) > 0:
        if args[0] == 'help':
            print_usage()
            sys.exit()
        good = args[0]
    if len(args) > 1:
        test = args[1]
    if len(args) > 2:
        repo_path = args[2]
    if len(args) > 3:
        bad = args[3]
    if len(args) > 4:
        build = args[4]
    if len(args) > 5:
        build_args = args[5:]

    run(test, bad, good, repo_path=path, build=build,
        build_args=build_args)
