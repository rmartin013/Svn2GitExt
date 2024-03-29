#! /usr/bin/python
# coding: utf-8

# depends on packages:
# git, subversion, git-svn, jq, curl, python-pip
#
# pip install termcolor

import os
import sys
import argparse
import subprocess
import string
from datetime import datetime
import tempfile
import xml.etree.ElementTree as ET
import getpass
import shlex
from termcolor import colored

try:
	import credentials
	username = credentials.username
	password = credentials.password
except:
	username = None
	password = None

gGitDirectoryPresentation = "Main GIT repository of project "

gScriptDir = os.getcwd()
gAuthorsFile = os.path.join(os.path.dirname(os.path.realpath(__file__)), "authors.txt")
if os.path.exists(gAuthorsFile) == False:
	gAuthorsFile = None

def pause():
	print colored("Press [Enter] key to continue...", 'green')
	key = sys.stdin.read(1)

def changeDir(directory):
	print colored("cd %s" % (directory), 'green')
	os.chdir(directory)

def askConfirmation(text):
	print colored("%s press [Y] followed [Enter] key to continue..." % (text), 'green')
	key = "0"
	while key != "Y" and key != "y":
		key = sys.stdin.read(1)

def mkpdir(path):
	try:
		os.makedirs(path, 0755)
	except:
		pass

class SvnInfo:
	def __init__(self, SvnWorkDir):
		app = subprocess.Popen(["svn", "info", SvnWorkDir], stdout = subprocess.PIPE, universal_newlines = True)
		for line in app.stdout:
			chunk = string.split(line, ": ")
			if chunk[0] == "URL":
				self.ProjectUrl = chunk[1].strip()
			elif chunk[0] == "Repository Root":
				self.RepoUrl = chunk[1].strip()
	def __repr__(self):
		return repr((self.ProjectUrl, self.RepoUrl))

def traceFn(cmd):
	print "==================="
	print colored(cmd, 'blue')
	print "==================="

def callCommand(cmd, trace = True, ret = False):
	if trace == True:
		traceFn(cmd)
	if ret == True:
		try:
			result = subprocess.check_output(shlex.split(cmd))
			print result
			return result
		except subprocess.CalledProcessError, e:
			print colored("Error %d happenned in %s, press [Enter] key to continue..." % (e.returncode, os.getcwd()), 'red')
			sys.stdin.read(1)
			return e.output
	else:
		error = os.system(cmd)
		if error != 0:
			print colored("Error %d happenned in %s, press [Enter] key to continue..." % (error, os.getcwd()), 'red')
			sys.stdin.read(1)

def gitSubtreeCmd(cmd, prefix, subtree):
	now = datetime.now()
	if cmd == "push":
		branch = "integration"
		direction = "to"
	else:
		branch = "master"
		direction = "from"
	return callCommand("git subtree %s --prefix=%s %s %s -m '%s changes %s SVN repo on (%s)'" % (cmd, prefix, subtree, branch, cmd, direction, now.strftime("%d/%m/%Y %H:%M:%S")), True, True)

def checkBitbucketProjectUrl(url):
	with tempfile.NamedTemporaryFile() as fp:
		os.system("curl -s -X GET -u '%s':'%s' %s > %s" % (username, password, url, fp.name))
		return subprocess.check_output(["jq", "-r", '.key', fp.name]).strip()

def getBitbucketCloneUrl(name):
	with tempfile.NamedTemporaryFile() as fp:
		callCommand("curl -s -X GET -u '%s':'%s' %s/%s > %s" % (username, password, gRemoteGitServerUrl, name, fp.name), False)
		return subprocess.check_output(["jq", "-r", '.links | .clone[] | select(.name=="ssh") | .href', fp.name]).strip()

def purgeBitbucketProject(pattern):
	with tempfile.NamedTemporaryFile() as fp:
		callCommand("curl -s -X GET -u '%s':'%s' %s > %s" % (username, password, gRemoteGitServerUrl, fp.name), False)
		for repo in subprocess.check_output(["jq", "-r", '.values[] | .slug', fp.name]).strip().split('\n'):
			if pattern is None or repo.startswith(pattern):
				if args.iterative:
					askConfirmation("Are you sure you want to delete %s repository?" % (repo))
				callCommand("curl -v -X DELETE -u '%s':'%s' %s/%s" %(username, password, gRemoteGitServerUrl, repo), False)
				print colored("\nDeleted %s succesfully" % (repo), 'blue')

def getFirstGitRevision():
	app = subprocess.Popen(["git", "rev-list", "--max-parents=0", "HEAD"], stdout = subprocess.PIPE, universal_newlines = True)
	return app.stdout.readlines()[-1].strip()

def createGitSvnSubtree(text):
	subtreePath = os.path.join(gLocalGitRepoBase, ext_name)

	# clone in local git repository using git svn
	callCommand("git svn clone -A %s --preserve-empty-dirs%s %s %s" % (gAuthorsFile, rev_opt, url, subtreePath))

	# Git push to a GIT server remote
	changeDir(subtreePath)

	# Append svn:ignore settings to the default git exclude file:
	callCommand("git svn show-ignore >> .git/info/exclude")

	if ext_name != gProjectName:
		# Git push to a GIT server remote
		clone_url = createGitRemote(ext_name, \
		text + ' translation to git subtree for cloning (svn - ' + url + rev_opt + ') into local directory: ' + directory)

		callCommand("git remote add origin " + clone_url)
		callCommand("git push -u origin --all")

		# Add git-subtree link in global project
		os.chdir(args.directory)
		callCommand("git remote add %s %s" % (ext_name, clone_url))
		createSubtreeCmd = 'git subtree add --prefix=%s %s master' % (directory, ext_name)
		traceFn(createSubtreeCmd)
		if os.system(createSubtreeCmd) == 256:
			# This error happens when the subtree creation is impossible because the prefix already exists.
			# The only effective workaround I know is to do the subtree creation in a branch created before the initial prefix creation, then merge it.
			callCommand("git checkout -b b-%s %s" % (ext_name, getFirstGitRevision()))
			callCommand(createSubtreeCmd)
			callCommand("git checkout master")
			callCommand('git merge "b-%s" -m "Integrated %s %s as a git subtree at %s"' % (ext_name, text, url, directory))
			callCommand('git branch -D "b-%s"' % (ext_name))
		with open("README", 'a') as readme:
			readme.write(" * %s : %s (svn - %s%s)\n" % (directory, ext_name, url, rev_opt))
		callCommand('git commit -am "Updated README with git subtree %s association"' % (directory))
		print "********************************************\n\n"

	# Pause execution, time to debug...
	if args.iterative:
		pause()

def getSvnExternalsTargetList(path):
	app = subprocess.Popen(["svn", "pg", "-R", "svn:externals", "--xml", path], stdout = subprocess.PIPE, universal_newlines = True)
	root = ET.parse(app.stdout)
	lst = []
	targets = []
	i = 0
	for target in root.findall("./target"):
		lst.append(target.get('path'))
		i += 1
	if i == 1:
		return lst[0]
	else:
		for target in lst:
			result = getSvnExternalsTargetList(target)
			if type(result) is list:
				targets += result
			else:
				targets.append(result)
		return targets

class SvnExternal:
	def __init__(self, url = None, directory = None, revision = None):
		self.url = url
		self.directory = directory
		self.revision = revision
	def __repr__(self):
		return repr((self.url, self.directory, self.revision))

class GitSubtree:
	def __init__(self, prefix = None, subtree = None, svnUptodate = False):
		self.prefix = prefix
		self.subtree = subtree
		self.svnUptodate = svnUptodate
	def __repr__(self):
		return repr((self.prefix, self.subtree, self.svnUptodate))

def completeSvnExtDirectory(target, ext):
	# Append target path to the directory path
	complete = os.path.relpath(os.path.join(target, ext.directory), args.svn)

	# Special check for ModuleEncrypt.py (svn externals directly on a file)
	if os.path.isfile(os.path.join(target, ext.directory)):
		complete = os.path.dirname(complete)
		ext.url = os.path.dirname(ext.url)

	ext.directory = complete

def getSvnExternal(target, externals):
	app = subprocess.Popen(["svn", "pg", "svn:externals", target], stdout = subprocess.PIPE, universal_newlines = True)
	for line in app.stdout:
		Ext = SvnExternal()
		chunks = string.split(line.strip(), ' ')
		lastIdx = len(chunks)-1
		for i in range(lastIdx):
			if "http" in chunks[i] or '^/' in chunks[i]:
				url = string.split(chunks[i],'@')
				if len(url) >= 2:
					Ext.revision = url[1]
				if "^/" in chunks[i]:
					Ext.url = SvnUrls.RepoUrl + url[0].strip('^')
				else:
					Ext.url = url[0]
			elif "-r" in chunks[i]:
				Ext.revision = chunks[i+1]
		Ext.directory = chunks[lastIdx]
		if Ext.url is not None:
			completeSvnExtDirectory(target, Ext)
			externals.append(Ext)

def createGitRemote(name, description):
	dir_option = '\'{"name": "' + name + '", "scm": "git", "is_private": "false", "fork_policy": "no_public_forks", "description": "' + \
		description + '"}\''

	# Create Bitbucket repository directly on server
	callCommand("curl -v -u '%s':'%s' -H \"Content-Type: application/json\" %s -d %s" % (username, password, gRemoteGitServerUrl, dir_option), False)
	return getBitbucketCloneUrl(name)

def getSvnExternalsList():
	# Move to script dir in order to manage relative paths
	os.chdir(gScriptDir)
	target_list = getSvnExternalsTargetList(args.svn)
	externals = []
	if type(target_list) is list:
		for target in target_list:
			getSvnExternal(target, externals)
	else:
		getSvnExternal(target_list, externals)
	externals.sort(key=lambda SvnExternal: SvnExternal.directory)
	return externals

def getGitRestApi(gitUrl):
	from urlparse import urlparse as urlp
	parsed = urlp(gitUrl.strip('/'))
	return [parsed.scheme + '://' + parsed.netloc + '/rest/api/1.0' + parsed.path, os.path.basename(parsed.path)]

if __name__ == "__main__":
	parser = argparse.ArgumentParser(description='Bi-directionnal utility for synchronising SVN archived project using many svn:externals links with GIT repository using other repositories with git subtree')
	parser.add_argument('command', choices=["create","update","purge"], help='Command among "create", update", "purge"')
	parser.add_argument('-d','--directory', help='Absolute path to the local GIT directory / Mandatory for create & update')
	parser.add_argument('-s','--svn', help='Path to the local SVN directory / Mandatory for create')
	parser.add_argument('-b','--bitbucket', help='Bitbucket (GIT) project URL / Mandatory for create & purge')
	parser.add_argument('-i','--iterative', help='Pause after each critical operation (only for create & purge)')
	parser.add_argument('-u','--username', help='Git repository username')
	parser.add_argument('-p','--password', help='Git repository password for [username]')
	parser.add_argument('-r','--root', action="store_true", help='Update root subtree, default is no (only for update)')
	parser.add_argument('-a','--authors', help='Path to a git-svn author file / Mandatory for create & update')
	parser.add_argument('-f','--filter', help='filter pattern for purge command: delete only repos whose name starts with that pattern')
	args = parser.parse_args()

	# ------ Parse generic arguments ------

	# If user passed credentials by arguments, overwrite file credentials if exist
	if args.username:
		username = args.username
	if args.password:
		password = args.password

	# Ask explicitly for them as we did not find out ones
	if username is None:
		username = raw_input("Git Username: ")
	if password is None:
		password = getpass.getpass("Password for %s: " % (username))

	if args.command != "purge":
		if args.authors:
			gAuthorsFile = args.authors
		if gAuthorsFile is None:
			print colored("You must provide an authors file for this operation.", 'red')
			sys.exit(1)
		if os.path.exists(gAuthorsFile) == False:
			print colored("Unable to open %s" %(gAuthorsFile), 'red')
			sys.exit(1)
		if args.directory is None:
			print colored("You must provide the local path where you want to build the GIT projects.", 'red')
			sys.exit(1)
		if os.path.exists(os.path.dirname(args.directory)) == False:
			print colored("Invalid path %s\nYou must provide an absolute path!" % (args.directory), 'red')
			sys.exit(1)

	if args.command != "update":
		if args.bitbucket is None:
			print colored("You must provide a BitBucket URL related to the project where you want to store your GIT repositories", 'red')
			sys.exit(1)
		[bbProjectRestUrl, bbProjectKey] = getGitRestApi(args.bitbucket)
		gRemoteGitServerUrl = bbProjectRestUrl + '/repos'
		if checkBitbucketProjectUrl(bbProjectRestUrl) != bbProjectKey:
			print colored("Unable to access %s project using %s/%s" % (bbProjectKey, username, password), 'red')
			sys.exit(1)

	if args.command == "create":
		if args.svn is None:
			print colored("You must provide a Subversion working directory to clone it to GIT repositories.", 'red')
			sys.exit(1)
		if os.path.exists(args.svn) == False:
			print colored("Unable to open %s" %(args.svn), 'red')
			sys.exit(1)

		gProjectName = os.path.basename(args.directory)
		gLocalGitRepoBase = os.path.dirname(args.directory)
		ext_dir = args.directory

		# Create parent project
		SvnUrls=SvnInfo(args.svn)
		url=SvnUrls.ProjectUrl
		mkpdir(ext_dir)
		changeDir(ext_dir)

		# clone in local git repository using git svn
		ext_name = gProjectName
		directory = "."
		rev_opt = ""
		createGitSvnSubtree("SVN main directory")

		with open("README", 'w') as readme:
			readme.write(gGitDirectoryPresentation + gProjectName + '\n\n')
			readme.write('The main SVN project "%s" is cloned in this repository. ' % (url))
			readme.write('Inside of it, there is a git subtree (check for the online definition)' + \
			' for each original svn:external definition of the main project.\n' + \
			'Here is the list of git subtree associations:\n\n')
		callCommand("git add README")
		callCommand("git commit -m 'Created GIT %s project, SVN clone of %s'" % (gProjectName, url))

		clone_url = createGitRemote(gProjectName, 'Main GIT project for ' + gProjectName + ', should mirror (svn - ' + url + ')')
		callCommand("git remote add origin " + clone_url)

		# Create git subtree projects
		i=0
		for external in getSvnExternalsList():
			i += 1
			print external
			if external.revision is None:
				rev_opt = ""
			else:
				rev_opt = " -rBASE:%s" % (external.revision)
			directory = external.directory
			ext_name = "%s-ext-%02d-%s" % (gProjectName, i, os.path.basename(directory))
			url = external.url
			createGitSvnSubtree("svn:externals")

		# Push to server
		callCommand("git push -u origin --all")

		print colored("Final check, brutal diff from SVN local workdir (must be up to date to be accurate) to local GIT repo", 'green')
		os.chdir(gScriptDir)
		callCommand("diff -r -q -x dl -x '.gitignore' -x '.svn' -x '.git' %s %s" % (args.directory, args.svn))

	elif args.command == "update":
		try:
			readme = os.path.join(args.directory, "README")
		except:
			print colored("You must provide a valid GIT --directory option: [%s]" % (args.directory), 'red')
			sys.exit(1)
		try:
			f = open(readme, 'r')
		except:
			print colored("Unable to open %s" %(readme), 'red')
			sys.exit(1)
		changeDir(args.directory)
		print "\n-> Working in %s" % (os.getcwd())
		callCommand("git checkout master")
		callCommand("git pull")

		# First build a sorted list of externals
		externals = []
		line = f.readline()
		if line:
			i = line.find(gGitDirectoryPresentation)
			if i != -1:
				ProjectName = line[i+len(gGitDirectoryPresentation):].strip()
				print "ProjectName: " + ProjectName
			while line:
				if ' * ' in line:
					sub = GitSubtree()
					sub.prefix = line.split(' ')[2]
					sub.subtree = line.split(' ')[4]
					if '-rBASE:' in line:
						end = " with fixed revision -> discard it for update"
					else:
						externals.append(sub)
						end = ""
					print "Found subtree %s related at %s to svn:external%s" % (sub.subtree, sub.prefix, end)
				line = f.readline()
		f.close()
		externals.sort(key=lambda GitSubtree: GitSubtree.prefix)
		print(externals)

		# Then for each of them, check if there is an update from SVN side
		for i in range(len(externals)):
			changeDir(os.path.join(args.directory, "../" + externals[i].subtree))
			print "\n-> Working in %s" % (os.getcwd())
			if "Current branch master is up to date." in callCommand("git svn rebase -A %s" % (gAuthorsFile), True, True):
				externals[i].svnUptodate = True
			else:
				callCommand("git pull")
				callCommand("git push")

		changeDir(args.directory)
		print "\n-> Working in %s" % (os.getcwd())
		pause()

		# Now reflect changes via git subtrees on main project from updated externals
		for i in range(len(externals)):
			if externals[i].svnUptodate == True:
				print "Skip git subtree pull on prefix %s / subtree %s" % (externals[i].prefix, externals[i].subtree) + \
				" as it was detected uptodate from SVN side"
			else:
				gitSubtreeCmd("pull", externals[i].prefix, externals[i].subtree)
		callCommand("git push")

		# Begin GIT -> SVN update via pushing changes on subtrees to externals projects
		for i in range(len(externals)):
			# Default: Always skip the root subtree except if asked by option --root
			if externals[i].prefix == gRootRepositoryName and not args.root:
				continue
			changeDir(args.directory)
			gitSubtreeCmd("push", externals[i].prefix, externals[i].subtree)
			changeDir(os.path.join(args.directory, "../" + externals[i].subtree))
			callCommand("git fetch origin")
			callCommand("git checkout integration")
			callCommand("git rebase origin/master")
			callCommand("git checkout master")
			callCommand("git merge")
			diffs = callCommand("git diff --compact-summary integration master", True, True)
			if(diffs != ""):
				print diffs
				callCommand("git log --left-right integration...master")
				askConfirmation("\nPlease check the logs above. If you see anything suspect, perform manually " + \
				"the merge between integration and master from %s\nOtherwise just" % (os.getcwd()))
				# If we continue, it is either we can merge or it has already been done manually
				callCommand("git checkout master")
				callCommand("git merge integration")
				callCommand("git push")
				callCommand("git push origin --delete integration")
				callCommand("git branch -D integration")

		# Convert GIT logs to SVN ones via git svn in 2 passes (dry-run for ultimate check,
		# then the real thing). If git-svn is correctly patched, it should correct every svn commit date & author
		for j in [0, 1]:
			if j == 0:
				step = "--dry-run"
				opt = step
			else:
				step = "for real!"
				opt = ""
			askConfirmation("Next step is to push your change to SVN repositories (%s)...\n" % (step) + \
			"It's good time to check everything is good before doing the synchronisation.\n" + \
			"When you are sure,")
			for i in range(len(externals)):
				changeDir(os.path.join(args.directory, "../" + externals[i].subtree))
				print "\n-> Working in %s" % (os.getcwd())
				callCommand("git checkout master")
				callCommand("git pull")
				callCommand("git svn dcommit -A %s %s" % (gAuthorsFile, opt))

		# Unfortunately, git-svn will rebase the external logs, thus we need to re-create from there
		# subtrees for updated externals
		for i in range(len(externals)):
			changeDir(os.path.join(args.directory, "../" + externals[i].subtree))
			callCommand("git fetch origin")
			if("Your branch and 'origin/master' have diverged" in callCommand("git status --ahead-behind", True, True)):
				callCommand("git push -f")
				changeDir(args.directory)
				callCommand("git rm -r %s" % (externals[i].prefix))
				callCommand("git commit -m 'Preparing to re-create [%s] subtree (delete old one)'" % (externals[i].prefix))
				callCommand("git subtree add --prefix=%s --squash %s master" % (externals[i].prefix, externals[i].subtree))
		callCommand("git push")

	elif args.command == "purge":
		purgeBitbucketProject(args.filter)
	else:
		print colored("Unknown command", 'red')
