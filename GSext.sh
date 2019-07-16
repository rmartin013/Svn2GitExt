#!/bin/bash

# ~/work/GS/GSext.sh ~/work/svn/conax/buildroot-CAP210_SDK_01.03.02_CertifConax/ ~/work/GS/CONAX/BuildRoot http://lac-ci-server:7990/rest/api/1.0/projects/CB/repos/
# ~/work/GS/GSext.sh ~/work/svn/projects/TRUNK/ ~/work/GS/CONAX/Appli/ http://lac-ci-server:7990/rest/api/1.0/projects/CA/repos/

# 		usage: GSext $SVN_REPO $LOCAL_GIT_REPO_BASE
# $SVN_REPO: SVN URL of project to migrate 
# $LOCAL_GIT_REPO_BASE: local directory where to migrate (one subdirectory per external)

AUTHORS_FILE="$(dirname $0)/authors.txt"

username=
password=

SVN_REPO=$1
LOCAL_GIT_REPO_BASE="$(dirname $2)"
ROOT_PROJECT_NAME="$(basename $2)"
REMOTE_GIT_SERVER_URL=${3%*/}

function trace {
	echo "==================="
	echo "$@"
	"$@"
	if [ "$?" != "0" ]; then
		read -p "Error happenned, press [Enter] key to continue..."
	fi
	echo "==================="
}

function get_external { 
	local repo
	local tmp=$(mktemp)
	svn pg -R svn:externals --xml $1 | grep path | awk -F '"' '{ print $2 }' > $tmp
	if [ "$(wc -l $tmp | awk '{print $1}')" = "1" ]; then
		cat $tmp
	else
		for repo in `cat $tmp`;	do 
			get_external $repo
		done
	fi
	rm $tmp; 
}

# GSclone $URL $TARGET_DIRECTORY
function GSclone {
	trace git svn clone -A $AUTHORS_FILE --preserve-empty-dirs $@
}

if [ -z "$username" -o -z "password" ]; then
	echo 'Please enter your Bitbucket credentials'
	echo 'Username?'
	read username
	echo 'Password?'
	read -s password  # -s flag hides password text	
fi

# Clone parent project
ext_dir="$LOCAL_GIT_REPO_BASE/$ROOT_PROJECT_NAME"
mkdir -p "$ext_dir" > /dev/null
url=$(svn info "$SVN_REPO" | egrep '^URL' | awk '{print $2}')
# clone in local git repository using git svn
GSclone "$url" "$ext_dir"

echo "********************************************"

i=0
# get list of externals target directories
for target in `get_external $SVN_REPO`; do
	# get list of externals
	IFS=$'\n'
	for line in `svn pg svn:externals $target`; do
		let "i++"
		# Look for a revision index at the begginning of the line
		# ex: -r 3727 https://srv-dtv-01.hq.k.grp/SmarDTV/CAM_LINUX/CAP210/SDK/BOOT/common/src/cblsp appli/sources/CNX_CARDLESS/config/src/MemoryBlock/cblsp
		tmp=${line##*-r }
		# no revision at the begginning
		if [ "$line" = "$tmp" ]; then
			tmp=${line%% *}
			url=${tmp%%@*}
			revision=${tmp##*@}
			directory=${line#* }
			# let's check in the url (url@revison)
			[ "$url" = "$revision" ] && unset revision
		else
			IFS=$' \n\t'; read -r revision url directory <<< "$tmp"
		fi

		# Special check for ModuleEncrypt.py
		if [ -f "$target/$directory" ]; then
			directory="$(dirname $directory)"
			url="$(dirname $url)"
		fi
		
		# Remove the absolute path related to the SVN local checkout
		directory="${target#*$(realpath $SVN_REPO)}/$directory"
		
		# Remove "begining/./end" if any 
		directory="${directory%*/.}"
		
		# Remove "/" at the end if any 
		directory="${directory#*/}"
		echo -e "-------\ntarget: $target\nline: $line\nurl: $url\nrevision: $revision\ndirectory: $directory\n-------\n"
		
		[ -n "$revision" ] && rev_opt="-rBASE:$revision" || unset rev_opt
		
		# Construct external name: ext-$index-last directory name
		ext_name="ext-$(printf "%02d" $i)-$(basename $directory)"
		ext_dir="$LOCAL_GIT_REPO_BASE/$ROOT_PROJECT_NAME-$ext_name"
		mkdir -p "$ext_dir" > /dev/null

		# clone in local git repository using git svn
		GSclone "$rev_opt" "$url" "$ext_dir"
		
		# Git push to a GIT server remote
		cd "$ext_dir"
		# http://bitbucket02:7990/rest/api/1.0/projects/CON/repos/
		curl -v -u "$username":"$password" -H "Content-Type: application/json" "$REMOTE_GIT_SERVER_URL" -d '{"name": "'"$ext_name"'", "scm": "git", "is_private": "false", "fork_policy": "no_public_forks" }'
		clone_url=$(jq -r '.links | .clone[] | select(.name=="ssh") | .href' <<< $(curl -s -X GET -u "$username":"$password" "$REMOTE_GIT_SERVER_URL"/"$ext_name"))
		trace git remote add origin "$clone_url"
		git push -u origin --all
		
		# Add git-subtree link in global project
		cd "$LOCAL_GIT_REPO_BASE/$ROOT_PROJECT_NAME"
		trace git remote add "$ext_name" "$clone_url"
		trace git checkout -b "b-$ext_name" $(git rev-list --max-parents=0 HEAD | tail -n 1)
		trace git subtree add --prefix="$directory" "$ext_name" master
		trace git checkout master
		trace git merge "b-$ext_name" -m "Integrated svn:externals $url as a git subtree"
		trace git branch -D "b-$ext_name"
		echo "********************************************"

		# Pause execution, time to debug...
		#read -p "Press [Enter] key to resume..."
	done
done

curl -v -u "$username":"$password" -H "Content-Type: application/json" "$REMOTE_GIT_SERVER_URL" -d '{"name": "'"$ROOT_PROJECT_NAME"'", "scm": "git", "is_private": "false", "fork_policy": "no_public_forks" }'
clone_url=$(jq -r '.links | .clone[] | select(.name=="ssh") | .href' <<< $(curl -s -X GET -u "$username":"$password" "$REMOTE_GIT_SERVER_URL"/"$ROOT_PROJECT_NAME"))
trace git remote add origin "$clone_url"
git push -u origin --all
