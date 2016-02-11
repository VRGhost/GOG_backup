import os
import json
import time
import shutil
import urlparse
import urllib
import re
import posixpath as pp

from selenium import webdriver
from selenium.webdriver.support import expected_conditions as EC

def get_timestamp():
	return time.time() # TODO: UTC timestamps.
	
def to_gog_url(tail):
	return urlparse.urljoin("https://www.gog.com/", tail)
	
def norm_path(path):
	return re.sub("\W+", "_", path)

def to_pp(fsPath):
	parts = []
	(head, tail) = os.path.split(fsPath)
	parts.append(tail)
	while head:
		(new_head, tail) = os.path.split(head)
		parts.insert(0, tail)
		if new_head == head:
			parts.insert(0, head)
			break
		else:
			head = new_head
	return pp.join(*parts)
	
def get_moved_fname(newDir, oldPath):
	"""Generate a new filename the 'oldPath' file will be stored under."""
	oldFname = os.path.basename(oldPath)
	expFname = os.path.join(newDir, oldFname)
	idx = 0
	while os.path.exists(expFname):
		idx += 1
		(name, ext) = os.path.splitext(oldFname)
		expFname = os.path.join(newDir, "{} ({}){}".format(name, idx, ext))
	assert not os.path.exists(expFname)
	return expFname
	

class GamesRegistry(object):
	"""An object that represents registry of all games belonging to the account."""
	
	def __init__(self):
		self._data = {
			"created": get_timestamp(), 
			"games": {}
		}
		
	def updated(self, gogGameData):
		gid = gogGameData["id"]
		if str(gid) in self._data["games"]:
			# A game had been update if its release date had changed
			# TODO: intelligent detection
			return False
		# A new game!
		return True
	
	def markUpdated(self, gogGameData):
		gid = gogGameData["id"]
		self._data["games"][str(gid)] = gogGameData.copy()
	
	def load(self, fobj):
		"""Load state from a file-like object."""
		self._data = json.load(fobj)
		
	def dump(self, fobj):
		"""Save state to a file-like object."""
		self._data["updated"] = get_timestamp()
		json.dump(self._data, fobj)

def get_settings():
	download_dir = os.path.join(
		os.path.abspath(os.path.dirname(__file__)),
		"GOG_Backup"
	)
	return (
		download_dir,
	)
	
def authorize(browser):
	"""Authorize @ gog.com, raise exception on failure"""
	browser.get(r"https://www.gog.com")
	# click the 'login' button
	browser.find_element_by_css_selector("a[ng-click='openLogin()']").click()
	# wait for the login dialogue to appear
	browser.find_element_by_id("GalaxyAccountsFrame")
	# ensure login success by locating the 'logout' element.
	browser.switch_to_default_content()
	browser.find_element_by_css_selector("a[ng-click='logout()']")
	return browser

def init_browser(download_dir):
	"""Create & Return web browser instance."""
	profile = webdriver.FirefoxProfile()
	profile.set_preference("browser.download.folderList", 2)
	profile.set_preference("browser.download.manager.showWhenStarting", False)
	profile.set_preference("browser.download.dir", download_dir)
	profile.set_preference("browser.helperApps.neverAsk.saveToDisk", "application/pdf, application/zip, application/x-zip, application/x-zip-compressed, application/download, application/octet-stream")
	profile.set_preference("pdfjs.disabled", True);

	browser = webdriver.Firefox(firefox_profile=profile)
	browser.implicitly_wait(60)
	return browser

def list_my_games(browser):
	"""Returns list of all game datas owned by the account"""
	browser.get(r"https://www.gog.com/account")
	data = json.loads(browser.execute_script("return JSON.stringify(gogData);"))
	return data["accountProducts"]

def do_atomic_download(url, browserDownloadDir, targetDir, timeout=3600):
	oldDirL = frozenset(os.listdir(browserDownloadDir))
	browser.get(url)
	
	# Here be a timezone/time change bug
	endTime = time.time() + timeout
	while time.time() < endTime:
		newL = frozenset(os.listdir(browserDownloadDir))
		newFiles = newL - oldDirL
		if newFiles:
			if not any(fname.endswith(".part") for fname in newFiles):
				for newF in newFiles:
					newF = os.path.join(browserDownloadDir, newF)
					movedFname = get_moved_fname(targetDir, newF)
					if os.stat(newF).st_size > 0:
						# A file had been downloaded!
						print "Detected a sucessfull download of {}".format(newF)
						if not os.path.exists(targetDir):
							os.makedirs(targetDir)
						shutil.move(
							newF,
							movedFname
						)
						return movedFname
		time.sleep(1)
	raise Exception("Download timeout")
	
def do_update(browser, game, downloadDir, rootDownloadDir):
	gameRoot = os.path.join(rootDownloadDir, game["slug"])
	if os.path.exists(gameRoot):
		# Move old version into the 'prev' child dir
		newParent = gameRoot + "_new"
		os.mkdir(newParent)
		os.rename(gameRoot, os.path.join(newParent, "prev"))
		os.rename(newParent, gameRoot)
	else:
		# A new game
		os.mkdir(gameRoot)
	# Save the timestamp
	with open(os.path.join(gameRoot, "timestamp.txt"), "wb") as fobj:
		fobj.write(str(get_timestamp()))
	infoUrl = r"https://www.gog.com/account/gameDetails/{}.json".format(game["id"])
	browser.get(infoUrl)
	src = browser.page_source
	sData = re.search(r"\{.*\}", src).group(0)
	gData = json.loads(sData)
	with open(os.path.join(gameRoot, "info.json"), "wb") as fobj:
		json.dump(gData, fobj)
		
	downloadList = {}
	
	for (lang, sub) in gData["downloads"]:
		for (platform, els) in sub.iteritems():
			for el in els:
				relUrl = el["manualUrl"]
				downloadUrl = to_gog_url(relUrl)
				if relUrl in downloadList:
					#Already downloaded
					continue
					
				localFname = do_atomic_download(
					downloadUrl, 
					downloadDir,
					os.path.join(gameRoot, "downloads", lang, platform)
				)
				downloadList[relUrl] = to_pp(os.path.relpath(localFname, gameRoot))
				
	for extra in gData["extras"]:
		type = extra["name"]
		relUrl = extra["manualUrl"]
		downloadUrl = to_gog_url(relUrl)
		if relUrl in downloadList:
			#Already downloaded
			continue
		localFname = do_atomic_download(
			downloadUrl,
			downloadDir,
			os.path.join(gameRoot, "extras", norm_path(type)),
		)
		downloadList[relUrl] = to_pp(os.path.relpath(localFname, gameRoot))
	
	with open(os.path.join(gameRoot, "file_list.json"), "wb") as fobj:
		json.dump(downloadList, fobj)
	
	# download the logo
	urllib.urlretrieve(
		to_gog_url(game["image"]) + "_200.jpg",
		os.path.join(gameRoot, "logo.jpg"),
	)
	
if __name__ == "__main__":
	(target_dir, ) = get_settings()
	
	print "Saving data to {}".format(target_dir)
	if not os.path.exists(target_dir):
		os.makedirs(target_dir)
		
	tmp_dir = os.path.join(target_dir, "tmp")
	if os.path.exists(tmp_dir):
		shutil.rmtree(tmp_dir)
		
	os.mkdir(tmp_dir)
		
	registry = GamesRegistry()
	regFile = os.path.join(target_dir, "backup.json")
	if os.path.isfile(regFile):
		with open(regFile, "rb") as fobj:
			registry.load(fobj)
			
	browser = init_browser(tmp_dir)
	authorize(browser)
	games = list_my_games(browser)
	for game in games:
		if registry.updated(game):
			do_update(browser, game, tmp_dir, target_dir)
			registry.markUpdated(game)
			with open(regFile, "wb") as fobj:
				registry.dump(fobj)
	
	browser.close()
	shutil.rmtree(tmp_dir)