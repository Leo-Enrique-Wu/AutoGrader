import argparse
import subprocess
import os
import sys
import re

from os import path

EXECUTE_REPEAT_TIMES = 4
SUBMISSION_FOLDER_NAME = "Submission attachment(s)"
N_1M = 1_000_000
N_10M = 10_000_000
P = 4
X = 3
resultFile = None
rootPath = ""

# Return (testResult, avgElapseTime)
def testing(N:int, x:int, expected:[int], processNum:int, repeatTimes:int, useWhitespaceSeparator:bool):
	
	print("N=%d, x=%d, processNum=%d, repeatTimes=%d" % (N, x, processNum, repeatTimes))
	
	# check for the correctness
	process = subprocess.Popen(["mpiexec", "-n", str(processNum), "./checkdiv", str(N), str(x)], \
	                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
	(out, err) = process.communicate()
	
	outputMsgs = out.decode("utf-8").splitlines()
	print("Output:")
	for outputMsg in outputMsgs:
		print(outputMsg)
	
	actual = []
	resultFileName = str(N) + ".txt"
	with open(resultFileName, 'r') as resultFile:
		for line in resultFile:
			if (useWhitespaceSeparator):
				partialStrActual = line.split(' ')
				# print(partialStrActual)
				for elementStr in partialStrActual:
					isNum = re.match("\d+", elementStr)
					if isNum:
						actual.append(int(elementStr))
			else:
				# use default separator(newline)
				actual.append(int(line.strip()))
	
	testResult = True
	#if (len(expected) != len(actual)):
	#	print("Testing Result Incorrect: len(expected)(=%d) != len(actual)(=%d)" % (len(expected), len(actual)))
	#	testResult = False
	#else:
		
	length = len(expected)
	for i in range(0, length):
		if (expected[i] != actual[i]):
			print("Testing Result Incorrect: Line %d, expected=%d, actual=%d" % (i + 1, expected[i], actual[i]))
			testResult = False
			break
	
	if (not testResult):
		return (testResult, None)
		
	# Get the avg elapse time
	totalElapseTime = 0.0
	
	envVarDict = dict(os.environ)
	envVarDict['TIMEFORMAT'] = '%R'
	
	for i in range(EXECUTE_REPEAT_TIMES):
		# --mca opal_warn_on_missing_libcuda 0 to subpress CUDA-aware support warning
		process = subprocess.Popen(["time", "mpirun", "-n", str(processNum), "--mca", "opal_warn_on_missing_libcuda", \
		                              "0", "./checkdiv", str(N), str(x)], \
		                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=envVarDict, shell=True)
		(out, err) = process.communicate()
	
		# time's result is in err
		outputMsgs = err.decode("utf-8").splitlines()
		print("Output:")
		for outputMsg in outputMsgs:
			print(outputMsg)
			elapseTime = float(outputMsg)
			totalElapseTime += elapseTime
	
	print("totalElapseTime=%f" % totalElapseTime)
	avgElapseTime = totalElapseTime / 4
	print("avgElapseTime=%f" % avgElapseTime)
	
	return (testResult, avgElapseTime)


def grade(studentName:str, specificStudent:bool, useWhitespaceSeparator:bool):
	
	folderName = studentName
	grade = 0
	comments = []
	
	netIdPattern = re.compile(r'\(\w+\d+\)')
	netIdMatches = netIdPattern.search(studentName)
	netId = netIdMatches.group()
	netId = netId.replace("(", "")
	netId = netId.replace(")", "")
	print('netId found: ' + netId)
	
	if (specificStudent):
		gradeFile = open("grade_{}.txt".format(netId), "w")
	else:
		gradeFile = open("grades.txt", "a")
	gradeFile.write(studentName + '\n')
	
	# Go to submission folder
	os.chdir(folderName)
	os.chdir(SUBMISSION_FOLDER_NAME)
	currentWorkingDirectory = os.getcwd()
	print("Change directory to %s" % currentWorkingDirectory)
	
	#process = subprocess.Popen(['ls', '-a'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
	#(out, err) = process.communicate()
	#out.decode("utf-8")
	
	# Unzip {netId}.zip
	findNoZipFile = False
	zipFileName = netId + ".zip"
	print("Unzipping file: %s" % zipFileName)
	process = subprocess.Popen(["unzip", "-o", zipFileName], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
	(out, err) = process.communicate()
	if process.returncode != 0: 
		print("Unzip failed %d %s %s" % (process.returncode, out, err))
		grade -= 1
		comments.append("-1: Didn't submit in a single zip file")
	
	# Check whether {netId}.c in the current working directory
	# 1. If "yes", then stay in the current working directory
	# 2. If "no", then change directory to ./{netId}
	programFileName = netId + ".c"
	if(not(path.exists(programFileName))):
		dir_list = os.listdir()
		for f in dir_list:
			if (path.isdir(f)):
				os.chdir(f)
				currentWorkingDirectory = os.getcwd()
				print("Change directory to %s" % currentWorkingDirectory)
				
				if(path.exists(programFileName)):
					break
				else:
					os.chdir("..")
	
	if(not path.exists(programFileName)):
		msg = "Error: Cannot find the programming file: %s" % programFileName
		print(msg)
		gradeFile.write(msg + '\n')
		gradeFile.write("=================================" + '\n')
		gradeFile.close()
		return
	
	# Compile `mpicc -lm -std=c99 -Wall -o checkdiv {netID}.c`
	print("Compiling with cmd: mpicc -lm -std=c99 -Wall -o checkdiv %s" % programFileName)
	process = subprocess.Popen(["mpicc", "-lm", "-std=c99", "-Wall", "-o", "checkdiv", programFileName], \
	                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
	(out, err) = process.communicate()
	
	hasWarning = False
	hasError = False
	errMsgs = err.decode("utf-8").splitlines()
	for errMsg in errMsgs:
		print("errMsg: %s" % errMsg)
		if "error" in errMsg:
			hasError = True
		if "warning" in errMsg:
			hasWarning = True
		if (hasError and hasWarning):
			break
	
	if (hasError):
		msg = "Has compile errors"
		print(msg)
		gradeFile.write(msg + '\n')
		gradeFile.write("=================================" + '\n')
		gradeFile.close()
		return
	
	if (hasWarning):
		print("Compiled with warnings")
	
	# Testing
	# 1. N = 1m, x = 3, p = 1
	# Check whether result is matched
	testResults = []
	testingResultCommentTemp = "-5: Testing failed: N={}, x={}, p={}"
	(t1TestResult, t1AvgElapseTime) = testing(N_1M, X, s1RefList, 1, EXECUTE_REPEAT_TIMES, useWhitespaceSeparator)
	t1AvgElapseTimeStr = str(t1AvgElapseTime) if not(t1AvgElapseTime is None) else "None"
	testResults.append(t1TestResult)
	if (not t1TestResult):
		comments.append(testingResultCommentTemp.format(N_1M, X, 1))
	print("t1's result: testResult=%s, avgElapseTime=%s" % (str(t1TestResult), t1AvgElapseTimeStr))
	
	# 2. N = 1m, x = 3, p = 4
	(t2TestResult, t2AvgElapseTime) = testing(N_1M, X, s1RefList, 4, EXECUTE_REPEAT_TIMES, useWhitespaceSeparator)
	t2AvgElapseTimeStr = str(t2AvgElapseTime) if not(t2AvgElapseTime is None) else "None"
	testResults.append(t2TestResult)
	if (not t2TestResult):
		comments.append(testingResultCommentTemp.format(N_1M, X, 4))
	print("t2's result: testResult=%s, avgElapseTime=%s" % (str(t2TestResult), t2AvgElapseTime))
	
	# 3. N = 10m, x = 3, p = 1
	(t3TestResult, t3AvgElapseTime) = testing(N_10M, X, s2RefList, 1, EXECUTE_REPEAT_TIMES, useWhitespaceSeparator)
	t3AvgElapseTimeStr = str(t3AvgElapseTime) if not(t3AvgElapseTime is None) else "None"
	testResults.append(t3TestResult)
	if (not t3TestResult):
		comments.append(testingResultCommentTemp.format(N_10M, X, 1))
	print("t3's result: testResult=%s, avgElapseTime=%s" % (str(t3TestResult), t3AvgElapseTime))
	
	# 4. N = 10m, x = 3, p = 4
	(t4TestResult, t4AvgElapseTime) = testing(N_10M, X, s2RefList, 4, EXECUTE_REPEAT_TIMES, useWhitespaceSeparator)
	t4AvgElapseTimeStr = str(t4AvgElapseTime) if not(t4AvgElapseTime is None) else "None"
	testResults.append(t4TestResult)
	if (not t4TestResult):
		comments.append(testingResultCommentTemp.format(N_10M, X, 4))
	print("t4's result: testResult=%s, avgElapseTime=%s" % (str(t4TestResult), t4AvgElapseTime))
	
	if (t1TestResult and t2TestResult):
		s1Speedup = t1AvgElapseTime / t2AvgElapseTime
		s1SpeedupStr = str(s1Speedup)
	else:
		s1Speedup = 1.0
		s1SpeedupStr = "Testing Failed"
	
	if (t3TestResult and t4TestResult):
		s2Speedup = t3AvgElapseTime / t4AvgElapseTime
		s2SpeedupStr = str(s2Speedup)
	else:
		s2Speedup = 1.0
		s2SpeedupStr = "Testing Failed"
	
	speedup = max(s1Speedup, s2Speedup)
	print("Speedup=%f: s1=%s, s2=%s" % (speedup, s1SpeedupStr, s2SpeedupStr))
	
	if (hasWarning):
		grade += 4
		comments.append("-1: Code compiles with some warnings")
	else:
		grade += 5
	
	for testResult in testResults:
		if (testResult):
			grade += 5
	
	# If there is a speedup, even small one, from four processes to one process in at 
	# at least one experiment --> 5 points
	if (speedup > 1.0):
		grade += 5
	else:
		comments.append("-5: There is no speedup: s1(N=1M)={}, s2(N=10M)={}".format(s1SpeedupStr, s2SpeedupStr))
	
	gradeFile.write("Grade: " + str(grade) + '\n')
	gradeFile.write("Comments: " + '\n')
	for comment in comments:
		gradeFile.write(comment + '\n')
	gradeFile.write("=================================" + '\n')
	gradeFile.close()
	
	return
	

if __name__ == "__main__":
	
	# Read Params
	parser = argparse.ArgumentParser(description='Lab 1 Autograder')
	parser.add_argument('--f', dest='folder', action='store', help="The name of the folder of submission")
	parser.add_argument('--id', dest='netId', action='store', help="The NetID of the student")
	parser.add_argument('--g', dest='genRef', action='store', help="Whether need to generate ref result? True or False")
	parser.add_argument('--ss', dest='wsSeperator', action='store', help="Use whitespace as a separator? True or False")
	args = parser.parse_args()
	
	folderName = args.folder
	netId = args.netId
	isGenRef = True if (args.genRef == "True") else False
	useWhitespaceSeparator = True if (args.wsSeperator == "True") else False
	print("Params:")
	print("Folder: %s" % folderName)
	print("isGenRef: %s" % isGenRef)
	
	# Generate ref result: either generate it or read from existed files
	s1RefList = []
	s2RefList = []
	if (isGenRef):
		
		print("Generate ref result")
		s1RefFile = open("1M_3_ref.txt", "w")
		s2RefFile = open("10M_3_ref.txt", "w")
		
		for i in range(2, N_1M + 1):
			if (i % X == 0):
				s1RefFile.write(str(i) + '\n')
				s1RefList.append(i)
				
		for i in range(2, N_10M + 1):
			if (i % X == 0):
				s2RefFile.write(str(i) + '\n')
				s2RefList.append(i)
				
	else:
		
		print("Read from ref result")
		s1RefFile = open("1M_3_ref.txt", "r")
		for line in s1RefFile:
			s1RefList.append(int(line))
		
		s2RefFile = open("10M_3_ref.txt", "r")
		for line in s2RefFile:
			s2RefList.append(int(line))
	
	rootPath = os.getcwd()
	
	if os.path.exists("grades.txt"):
			os.remove("grades.txt")
	
	if (folderName is None):
		dir_list = os.listdir()
		for f in dir_list:
			if (path.isdir(f)):
				grade(f, False, useWhitespaceSeparator)
				os.chdir(rootPath)
	else:
		grade(folderName, True, useWhitespaceSeparator)
		os.chdir(rootPath)
		
	print("Done!")