#! /usr/bin/python
# coding: utf-8

import os
import sys
import argparse
import subprocess
import string
from datetime import datetime
import tempfile
import xml.etree.ElementTree as ET
import getpass

try:
	import credentials
	username = credentials.username
	password = credentials.password
except:
	username = None
	password = None

gGitDirectoryPresentation = "Root GIT repository of project "
gRootRepositoryName="root"
gAuthorsFile = os.path.join(os.path.dirname(os.path.realpath(__file__)), "authors.txt")

def pause():
	print "Press [Enter] key to continue..."
	key = sys.stdin.read(1)

def askConfirmation(text):
	print "%s press [Y] followed [Enter] key to continue..." % (text)
	key = "0"
	while key != "Y" and key != "y":
		key = sys.stdin.read(1)

def mkpdir(path):
	try:
		os.makedirs(path, 0755)
	except:
		pass

def getSubversionUrl(svn_work_dir):
	app = subprocess.Popen(["svn", "info", svn_work_dir], stdout = subprocess.PIPE, universal_newlines = True)
	for line in app.stdout:
		chunk = string.split(line, ": ")
		if chunk[0] == "URL":
			return chunk[1].strip()
	return None

def callCommand(cmd, trace=True):
	if trace == True:
		print "==================="
		print cmd
		print "==================="
	error = os.system(cmd)
	if error != 0:
		print "Error %d happenned in %s, press [Enter] key to continue..." % (error, os.getcwd())
		sys.stdin.read(1)

def gitSubtreeCmd(cmd, prefix, subtree):
	now = datetime.now()
	if cmd == "push":
		branch = "integration"
	else:
		branch = "master"
	callCommand("git subtree %s -P %s %s %s -m '%s changes from SVN repo (%s)'" % (cmd, prefix, subtree, branch, cmd, now.strftime("%d/%m/%Y %H:%M:%S")))

def getBitbucketCloneUrl():
	with tempfile.NamedTemporaryFile() as fp:
		callCommand("curl -s -X GET -u '%s':'%s' %s/%s > %s" % (username, password, gRemoteGitServerUrl, ext_name, fp.name), False)
		return subprocess.check_output(["jq", "-r", '.links | .clone[] | select(.name=="ssh") | .href', fp.name]).strip()

def purgeBitbucketProject():
	with tempfile.NamedTemporaryFile() as fp:
		callCommand("curl -s -X GET -u '%s':'%s' %s > %s" % (username, password, gRemoteGitServerUrl, fp.name), False)
		for repo in subprocess.check_output(["jq", "-r", '.values[] | .slug', fp.name]).strip().split('\n'):
			callCommand("curl -v -X DELETE -u '%s':'%s' %s/%s" %(username, password, gRemoteGitServerUrl, repo), False)

def createGitSvnSubtree(text):
	ext_dir = os.path.join(gLocalGitRepoBase, "%s-%s" %(gRootProjectName, ext_name))
	mkpdir(ext_dir)

	# clone in local git repository using git svn
	callCommand("git svn clone -A %s --preserve-empty-dirs%s %s %s" % (gAuthorsFile, rev_opt, url, ext_dir))

	# Git push to a GIT server remote
	os.chdir(ext_dir)
	# http://bitbucket02:7990/rest/api/1.0/projects/CON/repos/
	dir_option = '\'{"name": "' + ext_name + '", "scm": "git", "is_private": "false", "fork_policy": "no_public_forks", "description": "' + \
	text + ' translation to git subtree for cloning (svn - ' + url + rev_opt + ') into local directory: ' + directory + '"}\''

	# Create Bitbucket repository directly on server
	callCommand("curl -v -u '%s':'%s' -H \"Content-Type: application/json\" %s -d %s" % (username, password, gRemoteGitServerUrl, dir_option), True)
	clone_url = getBitbucketCloneUrl()
	callCommand("git remote add origin " + clone_url)
	callCommand("git push -u origin --all")

	# Add git-subtree link in global project
	os.chdir(args.directory)
	callCommand("git remote add %s %s" % (ext_name, clone_url))
	#callCommand("git checkout -b b-%s $(git rev-list --max-parents=0 HEAD | tail -n 1)" % (ext_name))
	callCommand('git subtree add --prefix=%s %s master' % (directory, ext_name))
	#callCommand("git checkout master")
	#callCommand('git merge "b-%s" -m "Integrated %s %s as a git subtree at %s' % (ext_name, text, url, directory))
	#callCommand('git branch -D "b-%s"' % (ext_name))
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
	def setUrl(self, url):
		self.url = url
	def setDirectory(self, directory):
		self.directory = directory
	def setRevision(self, revision):
		self.revision = revision
	def __init__(self, url = None, directory = None, revision = None):
		self.setUrl(url)
		self.setDirectory(directory)
		self.setRevision(revision)
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

	# Append again Root repository name
	complete = os.path.join(gRootRepositoryName, complete)
	
	# Special check for ModuleEncrypt.py (svn externals directly on a file)
	if os.path.isfile(os.path.join(target, ext.directory)):
		complete = os.path.dirname(complete)
		ext.setUrl(os.path.dirname(ext.url))

	ext.setDirectory(complete)

def getSvnExternal(target, externals):
	app = subprocess.Popen(["svn", "pg", "svn:externals", target], stdout = subprocess.PIPE, universal_newlines = True)
	for line in app.stdout:
		Ext = SvnExternal()
		chunks = string.split(line.strip(), ' ')
		lastIdx = len(chunks)-1
		for i in range(lastIdx):
			if "http" in chunks[i]:
				url = string.split(chunks[i],'@')
				if len(url) >= 2:
					Ext.setRevision(url[1])
				Ext.setUrl(url[0])
			elif "-r" in chunks[i]:
				Ext.setRevision(chunks[i+1])
		Ext.setDirectory(chunks[lastIdx])
		if Ext.url is not None:
			completeSvnExtDirectory(target, Ext)
			externals.append(Ext)

def getSvnExternalsList():
	target_list = getSvnExternalsTargetList(args.svn)
	externals = []
	if type(target_list) is list:
		for target in target_list:
			getSvnExternal(target, externals)
	else:
		getSvnExternal(target_list, externals)
	externals.sort(key=lambda SvnExternal: SvnExternal.directory)
	return externals

if __name__ == "__main__":
	parser = argparse.ArgumentParser(description='Bi-directionnal utility for synchronising SVN archived project using many svn:externals links with GIT repository using other repositories with git subtree')
	parser.add_argument('command', choices=["create","update","purge"], help='Command among "create", update", "purge"')
	parser.add_argument('-d','--directory', help='Path to the local GIT directory / Mandatory')
	parser.add_argument('-s','--svn', help='Path to the local SVN directory / Mandatory for create')
	parser.add_argument('-b','--bitbucket', help='Bitbucket (GIT) project URL / Mandatory for create')
	parser.add_argument('-i','--iterative', help='Pause after each critical operation')
	parser.add_argument('-u','--username', help='Git repository username')
	parser.add_argument('-p','--password', help='Git repository password for [username]')
	args = parser.parse_args()

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

	if args.command == "create":
		gRootProjectName = os.path.basename(args.directory)
		gLocalGitRepoBase = os.path.dirname(args.directory)
		ext_dir = args.directory
		gRemoteGitServerUrl = args.bitbucket.strip('/')

		# Create parent project
		url=getSubversionUrl(args.svn)
		mkpdir(ext_dir)
		os.chdir(ext_dir)
		callCommand("git init")
		with open("README", 'w') as readme:
			readme.write(gGitDirectoryPresentation + gRootProjectName + '\n')
			readme.write('In this repository, the main SVN project "%s" is cloned in the git directory "%s". ' % (url, gRootRepositoryName))
			readme.write('Inside of it, there is a git subtree (check for the online definition)' + \
			' for each original svn:external definition of the main project.\n' + \
			'Here is the list of git subtree associations:\n')
		callCommand("git add README") 
		callCommand("git commit -m 'Created GIT %s project, SVN clone of %s'" % (gRootProjectName, url))

		# clone in local git repository using git svn
		ext_name = gRootRepositoryName
		directory = ext_name
		rev_opt = ""
		createGitSvnSubtree("SVN root directory")

		dir_option = '\'{"name": "' + gRootProjectName + '", "scm": "git", "is_private": "false", "fork_policy": "no_public_forks", "description": "' + \
		'Main GIT project for ' + gRootProjectName + ', should mirror (svn - ' + url + ')"}\''

		# Create Bitbucket repository directly on server
		callCommand("curl -v -u '%s':'%s' -H \"Content-Type: application/json\" %s -d %s" % (username, password, gRemoteGitServerUrl, dir_option), False)
		ext_name = gRootProjectName
		clone_url = getBitbucketCloneUrl()

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
			ext_name = "ext-%02d-%s" % (i, os.path.basename(directory))
			url = external.url
			createGitSvnSubtree("svn:externals")

		# Push to server
		callCommand("git push -u origin --all")

	elif args.command == "update":
		#print (args.directory)
		readme = os.path.join(args.directory, "README")
		f = open(readme, 'r')
		os.chdir(args.directory)
		print "\n-> Working in %s" % (os.getcwd())
		callCommand("git checkout master")
		callCommand("git pull")
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
						print "Found subtree %s related at %s to svn:external with fixed revision -> discard it for update" % (sub.subtree, sub.prefix)
					else:
						externals.append(sub)
						print "Found subtree %s related at %s to svn:external" % (sub.subtree, sub.prefix)
				line = f.readline()
		f.close()
		externals.sort(key=lambda GitSubtree: GitSubtree.prefix)
		print(externals)
		
		for i in range(len(externals)):
			os.chdir(os.path.join(args.directory, "../" + ProjectName + "-" + externals[i].subtree))
			print "\n-> Working in %s" % (os.getcwd())
			callCommand("git svn rebase -A %s" % (gAuthorsFile))
			callCommand("git pull")
			callCommand("git push")
			
		os.chdir(args.directory)
		print "\n-> Working in %s" % (os.getcwd())
		pause()
		
		for i in range(len(externals)):
			gitSubtreeCmd("pull", externals[i].prefix, externals[i].subtree)
		callCommand("git push")

		for i in range(len(externals)):
			gitSubtreeCmd("push", externals[i].prefix, externals[i].subtree)
			askConfirmation("Please perform manually the merge between integration and master from %s, then " % (externals[i].subtree))
			# Remove remaining integration branch (if still exists)
			callCommand("git push %s --delete integration" % (externals[i].subtree))

		askConfirmation("Next step is to push your change to SVN repositories...\n" + \
		"It's good time to check everything is good before doing the synchronisation.\nWhen you are sure, ")
		for i in range(len(externals)):
			os.chdir(os.path.join(args.directory, "../" + ProjectName + "-" + externals[i].subtree))
			print "\n-> Working in %s" % (os.getcwd())
			callCommand("git checkout master")
			callCommand("git branch -d integration")
			callCommand("git pull")
			callCommand("git svn dcommit -A %s" % (gAuthorsFile))

	elif args.command == "purge":
		gRemoteGitServerUrl = args.bitbucket.strip('/')
		purgeBitbucketProject()
	else:
		print("Unknown command")
