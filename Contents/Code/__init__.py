#!/usr/bin/python
# coding=utf-8

import string, os, urllib, codecs, json, copy, zipfile, re, time, datetime, requests, sys
from unrar import rarfile

from lxml import html

logEnabled = True
domain = "http://altyazi.org"
searchUrl = "http://google.com/search?site=webhp&source=hp&btnI=1&q=site:altyazi.org+"

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/48.0.2564.109 Safari/537.36',
			'Content-Type': 'application/x-www-form-urlencoded',			
			'Origin': 'http://altyazi.org',
			"Cache-Control": "max-age=0",
			"DNT": "1",
			"Accept-Language": "en-US,en;q=0.8,tr;q=0.6,fr;q=0.4",
			"Upgrade-Insecure-Requests": "1",
			"Accept":"text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"	}			


class LinkItem(object):
	def __init__(self, desc, link, isPackage):
		self.Desc = desc
		self.Link = link
		self.IsPackage = isPackage

class ContentLinkItem(object):
	def __init__(self, name, link):
		self.Name = name
		self.Link = link
		return

class SubInfo():
	def __init__(self, lang, url, sub, name):
		self.lang = lang
		self.url = url
		self.sub = sub
		self.name = name
		self.ext = string.split(self.name, '.')[-1]

def getFileSuffix(fileName):
	
	fileNameClear = {"720p","1080p","x264-","x265-","HDTV","WEBRip-",".avi",".mp4",".mkv" }
	fileName = fileName.lower()

	for clear in fileNameClear:		
		fileName = fileName.replace(clear,"")

	validSuffixes = {"ASAP","LOL","DIMENSION","QUEENS","ROVERS","AFG","mSD","SVA","FUM","KILLERS","BATV","FLEET","DEMAND","ETRG","RARBG","BORDERLiNE","KiNGS","CtrlHD","DRACULA"}
	suffix = fileName.split(".")[-1]

	for validSuffix in validSuffixes:
		if validSuffix.lower() == suffix:
			return suffix

	return ""

def getContentLink(contentName):	

	showPaths = []

	if Data.Exists("ShowPaths.data"):		
		showPathsStr = Data.Load("ShowPaths.data")
		showPathsStr = showPathsStr.strip()
		if len(showPathsStr)>0:
			showPathsStrArr = showPathsStr.split("|")
			for showPathsStrArrItem in showPathsStrArr:
				showPathsStrArrItemArr = showPathsStrArrItem.split("::")
				showPaths.append(ContentLinkItem(showPathsStrArrItemArr[0],showPathsStrArrItemArr[1]))
	
	if len(showPaths)>0:
		for showPath in showPaths:
			if showPath.Name.lower() == contentName.lower():
				return showPath.Link
	
	response = requests.get(searchUrl+contentName)
	tree = html.fromstring(response.content)	

	links = tree.xpath("//div[@id='ires']//a")
	if len(links)>0:
		showPath = links[0].attrib["href"].strip("/url?q=")		
		showPaths.append(ContentLinkItem(contentName, showPath))		

		dataToSave=""
		for path in showPaths:
			if len(dataToSave)>0:
				dataToSave = dataToSave+"|"
			dataToSave = dataToSave + path.Name +"::"+path.Link

		Data.Save("ShowPaths.data", dataToSave)

		return showPath

	return ""

def getSubtitle(path, isPackage, season, episode):
	
	page = requests.get(domain + path)

	cookies = page.cookies
	fileName = ""
	subArchive = []

	siList=[]

	try:
		tree = html.fromstring(page.content)
		postc = tree.xpath("//*[@name='postc']")[0].attrib['value']
		id = tree.xpath("//*[@name='id']")[0].attrib['value']	

		data = {"y": "12", "x": "86", "id": id, 'postc': postc }
		data = urllib.urlencode(data)

		response = requests.post(domain+"/indir.php", headers = headers, data = data, cookies = cookies)

		fileName = postc+".rar"

		Data.Save(fileName, response.content)		

		Log("Subtitle: " + fileName + " has succesfully downloaded")

		archive = rarfile.RarFile("DataItems/"+fileName)

		subArchive = archive.infolist()

		Log("RAR Items: %s" % len(subArchive))
		Log(archive.namelist())

	except:
		e = sys.exc_info()[0]
		Log(fileName + " error on downloading occured: " + str(e))
		return siList

	for parse in subArchive:

		name = parse.filename		

		if not name.lower().split(".")[-1] == "srt":
			continue

		if isPackage:
			seasonEpisode = ".s"+season.rjust(2,str("0"))+"e"+episode.rjust(2,str("0"))+"." #.S07E14.
			seasonEpisodeShort = "."+season+episode+"."										#.714.

			if not seasonEpisode in name.lower() and not seasonEpisodeShort in name.lower():
				continue
			else:
				Log("Extracting file from package: "+name)				

		legFile = archive.read_files(name)
		subData = legFile[0][1]
		try:
			subData = subData.decode("UTF-8")
		except:
			subData = subData.decode("ISO-8859-9")

		subData = subData.encode("UTF-8")
		
		subReg = domain + path + "/score=100&leg=" + name
		si = SubInfo("tr", subReg, subData, name)
		siList.insert(0, si)		
		
		#Dict[data['Filename'] + ' - ' + subUrl] = subReg

		#Data.Save(name, subData)

		break

	Data.Remove(fileName)

	return siList

def getPageDirectly(contentName, fileName):

	result = []
	response = requests.get(getContentLink(contentName))

	tree = html.fromstring(response.content)
	directElement = tree.xpath("//*[contains(., '"+fileName+"')] [not(.//*[contains(., '"+fileName+"')])]")

	if len(directElement)>0 :
		for contentElement in directElement:
			content = contentElement.getparent().getparent().getparent().getparent().getprevious()	#link path
			# check for en or tr
			link = content[1][0].attrib['href']
			lang = content[1].text_content().encode("utf-8")
			if "Türkçe" in lang or "türkçe" in lang:
				result = getSubtitle(link, False, "0", "0")

	return result

def getPageByScan(contentName, season, episode, filesuffix):

	result = []
	page = requests.get(getContentLink(contentName))

	tree = html.fromstring(page.content)
	episodes = tree.xpath("//div[contains(@id,'sezon_inf_')]")

	if len(episodes)>0 :

		linkItems=[]
		for contentElement in episodes:

			episodeName = contentElement.text_content().encode("utf-8").strip("<b>").strip("</b>").strip("\r").strip("\n")
			episodeName = episodeName.replace("Sezon : ","S").replace(" Bölüm : ","E")
			description = contentElement.getparent().getparent().getnext()[0].text_content().encode("utf-8")			

			if episodeName.lower() == "s"+season+"e"+episode or episodeName.lower() == "s"+season+"epaket":
				
				isPackage =  episodeName.lower() == "s"+season+"epaket"
				content = contentElement.getparent().getparent().getparent().getparent().getparent().getprevious() #linkpath
				link = content[1][0].attrib['href']
				lang = content[1].text_content().encode("utf-8")

				if "türkçe" in lang.lower():
					linkItems.append(LinkItem(description.lower(),link, isPackage))
		
		if len(linkItems)>0:
			for linkItem in linkItems:
				if len(filesuffix)>0 and filesuffix.lower() in linkItem.Desc:
					Log("get file by suffix " + linkItem.Link)
					result = getSubtitle(linkItem.Link, linkItem.IsPackage, season, episode)

			if not result:
				Log("get file by first valid subtitle " + linkItems[0].Link)
				result = getSubtitle(linkItems[0].Link, linkItem.IsPackage, season, episode)

	return result

def Start():	
	Log("START CALLED")

#class altyaziorgAgentMovies(Agent.Movies):
	#name = 'altyazi.org'
	#languages = [Locale.Language.Turkish]
	#primary_provider = False
	# contributes_to = ['com.plexapp.agents.freebase','com.plexapp.agents.freebase.the-movie-database']

	#def search(self, results, media, lang):
		#Log("MOVIE SEARCH CALLED")		

	#def update(self, metadata, media, lang):
		#Log("MOVIE UPDATE CALLED")

class altyaziorgAgentTvShows(Agent.TV_Shows):
	name = 'altyazi.org'
	languages = [Locale.Language.Turkish]
	primary_provider = False	
	skipExistingSubtitles = True
	# contributes_to = ['com.plexapp.agents.thetvdb','com.plexapp.agents.the-movie-database']

	def doScan(self, media, lang):		

		for season in media.seasons:
			for episode in media.seasons[season].episodes:
				for item in media.seasons[season].episodes[episode].items:
					for part in item.parts:
		
						if self.skipExistingSubtitles:

							hasSubtitle = False

							for subtitle in part.subtitles["tr"]:
								if "altyazi.org" in subtitle:
									Log("This content already has a turkish subtitle from altyazi.org: "+ subtitle)
									hasSubtitle = True
									continue

							if hasSubtitle:
								continue

						data = {}
						data["Name"] = str(media.title).translate(None,":")
						data["Season"] = str(season)
						data["Episode"] = str(episode).rjust(2,str("0"))
						data["Filename"] = string.split(str(part.file),os.sep)[-1].strip()
						
						Log("Data is: %s" % str(data))

						result = getPageDirectly(data["Name"], data["Filename"])

						if not result:
							siList = getPageByScan(data["Name"], data["Season"], data["Episode"], getFileSuffix(data["Filename"]))	
							for si in siList:					
								part.subtitles[Locale.Language.Match(si.lang)][si.url] = Proxy.Media(si.sub, ext=si.ext, format=si.ext) 
								Log("Subtitle updated for %s s%se%s" % (data["Name"], data["Season"], data["Episode"]))

	def search(self, results, media, lang):
		Log("TvSearch. Lang: " + lang)		
		try:
			self.doScan(media, lang)
		except:
			e = sys.exc_info()[0]
			Log("Error occured at doScan: " + str(e))

	def update(self, metadata, media, lang):
		Log("TvUpdate. Lang: " + lang)		
		try:
			self.doScan(media, lang)
		except:
			e = sys.exc_info()[0]
			Log("Error occured at doScan: " + str(e))