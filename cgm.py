import datetime
import csv
import sys
from dateutil.relativedelta import *
import copy
import os

year = 2022
date_format = "%Y-%m-%d %H:%M:%S"
this_year_start = str(year)+"-01-01 00:00:00"
next_year_start = str(year+1)+"-01-01 00:00:00"

# order 0=LIFO, 1=FIFO
order = 0

# expected sales header:
sales_header = ["date","platform","asset","cash","vol"]
# expected basis header:
basis_header = ["date","platform","asset","cash","vol","left"]

outdir = "output/"
sales_fn = "all_sales_"+str(year)+".csv"
basis_fn = "master_basis_"+str(year)+".csv"
basis_new_fn = outdir+"master_basis_result_"+str(year)+".csv"
matches_fn = outdir+"matched_trades_"+str(year)+".csv"
summary_fn = outdir+str(year)+"_summary.csv"

if not os.path.isdir(outdir):
	os.mkdir(outdir)

def gettime(s):
	return datetime.datetime.strptime(s, date_format)

# ------------
print("CGM Version ", version)
if order==0:
	print("Using LIFO matching")
else:
	print("Using FIFO matching")

f1 = open(sales_fn,"r")
f2 = open(basis_fn,"r")
f3 = open(basis_new_fn,"w")
f4 = open(matches_fn,"w")
f5 = open(summary_fn,"w")

def close_files():
	f1.close()
	f2.close()
	f3.close()
	f4.close()
	f5.close()

sales = csv.reader(f1)
buys = csv.reader(f2)
buys_new = csv.writer(f3)
matches = csv.writer(f4)
sum_w = csv.writer(f5)

# Check input files" headers
if next(sales) != sales_header:
	print("unexpected sales header")
	close_files()
	sys.exit()

if next(buys) != basis_header:
	print("unexpected basis header")
	close_files()
	sys.exit()

BUYVOL = 0			# asset buy volume this year
SELLVOL = 1			# asset sell volume this year
ASSETGAIN = 2		# asset gained this year
BASISCREATED = 3	# basis created this year after new matches
OLDBASISUSED = 4	# basis used from before this year after new matches
OLDBASIS = 5		# basis before this year before new matches
NEWBASIS = 6		# total basis including this year after matches
GAINUSD = 7			# usd gains this year
SCAPGAIN = 8		# short term capital gains
LCAPGAIN = 9		# long term capital gains

t_stat = [0.0]*10
stats = {}

# Check time ordering of sales
# sales should be in chrono order
s = 0
sellvol = {}
for sale in sales:
	sale_date = gettime(sale[0])
	asset = sale[2]
	if s == 0:
		last_sale_date = sale_date
	if asset not in sellvol:
		sellvol[asset] = 0.0
	if float(sale[4]) <= 0.0:
		print("non-positive sale vol detected")
		close_files()
		sys.exit()
	if sale_date < last_sale_date:
		print("wrong sale ordering")
		close_files()
		sys.exit()
	sellvol[asset] += float(sale[4])
	last_sale_date = sale_date
	s += 1
f1.seek(0)
next(sales)

# check time ordering of basis
# populate old leftover basis
b = 0
bc = {}
old_left = {}
for buy in buys:
	asset = buy[2]
	buy_date = gettime(buy[0])
	if b == 0:
		last_buy_date = buy_date
	if asset not in bc:
		bc[asset] = 0
		old_left[asset] = []
		stats[asset] = t_stat.copy()
	if float(buy[5]) < 0.0:
		print("error: negative leftover basis detected!")
		close_files()
		sys.exit()
	if (order==0 and (buy_date > last_buy_date)) or (order==1 and (buy_date < last_buy_date)):
		print("wrong buy ordering")
		close_files()
		sys.exit()
	if buy_date >= gettime(this_year_start) and buy_date < gettime(next_year_start):
		stats[asset][BUYVOL] += float(buy[4])
	bc[asset] += 1
	old_left[asset].append(float(buy[5]))
	if buy_date < gettime(this_year_start):
		stats[asset][OLDBASIS] += float(buy[5])
	last_buy_date = buy_date
	b += 1
f2.seek(0)
next(buys)

out_header = ["sale date","sale platform","asset","sale cash","vol","purch date","purch platform","purch cash","gain","term"]

# Write the headers for the matches file and buys_new file
matches.writerow(out_header)
buys_new.writerow(basis_header)

match = ['']*len(out_header) # 10

s = 0
b = 0
m = 0
vol = 0.0

# copy new_left from old_left to keep track of updated basis
new_left = copy.deepcopy(old_left)

# Construct matches and write match info to file and used basis to buys_new
for sale in sales:
	sale_date = gettime(sale[0])
	o_sale = float(sale[4])
	sale_rem = o_sale
	asset = sale[2]
	b = 0
	for a in bc:
		bc[a] = 0
	for buy in buys:
		buy_date = gettime(buy[0])
		if asset == buy[2] and sale_date >= buy_date and new_left[asset][bc[asset]] != 0.0:
			if sale_rem > new_left[asset][bc[asset]]:
				# using portion of sale
				vol = new_left[asset][bc[asset]]
				sale_rem -= vol
				new_left[asset][bc[asset]] = 0.0
			else:
				# using portion of buy
				vol = sale_rem
				new_left[asset][bc[asset]] -= vol
				sale_rem = 0.0
			buy_cash = (vol/(float(buy[4])))*float(buy[3])
			sale_cash = (vol/o_sale)*float(sale[3])
			stats[asset][SELLVOL] += vol
			match[0] = sale[0]
			match[1] = sale[1]
			match[2] = sale[2]
			match[3] = sale_cash
			match[4] = str(vol)
			match[5] = buy[0]
			match[6] = buy[1]
			match[7] = buy_cash
			gain = sale_cash - buy_cash
			match[8] = str(gain)
			stats[asset][GAINUSD] += gain
			time_dif = relativedelta(sale_date, buy_date).years
			if time_dif >= 1:
				match[9] = "longterm"
				stats[asset][LCAPGAIN] += gain
			elif time_dif >= 0 and time_dif < 1:
				match[9] = "shortterm"
				stats[asset][SCAPGAIN] += gain
			else:
				print("error: negative date difference!")
				print("sale: ",s," buy: ",b," vol: ",vol)
				close_files()
				sys.exit()
			matches.writerow(match)
			m += 1
			if sale_rem == 0.0:
				break
		b += 1
		bc[buy[2]] += 1
	if sale_rem != 0.0:
		print("error: couldn't find basis for sale#: ",s)
		close_files()
		sys.exit()
		
	f2.seek(0)
	next(buys)
	s += 1

for a in stats:
	if a not in sellvol:
		sellvol[a] = 0.0
	if abs(stats[a][SELLVOL] - sellvol[a]) > 0.000001:
		print("error: sell volume mismatch")
		print(">\tstats: ",stats[a][SELLVOL])
		print(">\tsellv: ",sellvol[a])
		close_files()
		sys.exit()

# write new basis file
# and also record stats on new basis
b = 0
for a in bc:
	bc[a] = 0
buyrow = ['']*6
for buy in buys:
	asset = buy[2]
	buy_date = gettime(buy[0])
	buyrow[0] = buy[0]
	buyrow[1] = buy[1]
	buyrow[2] = asset
	buyrow[3] = buy[3]
	buyrow[4] = buy[4]
	buyrow[5] = new_left[asset][bc[asset]]
	buys_new.writerow(buyrow)
	if buy_date >= gettime(this_year_start):
		stats[asset][BASISCREATED] += new_left[asset][bc[asset]]
	elif buy_date < gettime(this_year_start):
		stats[asset][OLDBASISUSED] += old_left[asset][bc[asset]] - new_left[asset][bc[asset]]
	else:
		print("error: non-existent buy date")
		close_files()
		sys.exit()
	bc[asset] += 1
	b += 1

# NEWBASIS = sum of new basis (after trades)
for asset in new_left:
	for x in new_left[asset]:
		stats[asset][NEWBASIS] += x

# ASSETGAIN = BUYVOL - SELLVOL
for asset in stats:
	stats[asset][ASSETGAIN] = stats[asset][BUYVOL] - stats[asset][SELLVOL]

# These are defined above, just copied here for convenience
#BUYVOL = 0			# asset buy volume this year
#SELLVOL = 1		# asset sell volume this year
#ASSETGAIN = 2		# asset gained this year
#BASISCREATED = 3	# basis created this year after new matches
#OLDBASISUSED = 4	# basis used from before this year after new matches
#OLDBASIS = 5		# basis before this year before new matches
#NEWBASIS = 6		# total basis including this year after matches
#GAINUSD = 7		# usd gains this year
#SCAPGAIN = 8		# short term capital gains
#LCAPGAIN = 9		# long term capital gains

sum_h = ['ASSET','BUYVOL','SELLVOL','ASSETGAIN','BASISCREATED','OLDBASISUSED','OLDBASIS','NEWBASIS','GAINUSD','SCAPGAIN','LCAPGAIN']

totals = ['Sum','','','','','','','']
GAINUSD_T = 0.0
SCAPGAIN_T = 0.0
LCAPGAIN_T = 0.0
for asset in stats:
	GAINUSD_T += stats[asset][GAINUSD]
	SCAPGAIN_T += stats[asset][SCAPGAIN]
	LCAPGAIN_T += stats[asset][LCAPGAIN]
totals.append(str(GAINUSD_T))
totals.append(str(SCAPGAIN_T))
totals.append(str(LCAPGAIN_T))

sum_w.writerow(sum_h)
for asset in stats:
	stats[asset].insert(0,asset)
	sum_w.writerow(stats[asset])
sum_w.writerow(totals)

print("Saved",m,"matches to",matches_fn)
print("Saved",b,"modified basis to",basis_new_fn)
print("Summary written to",summary_fn)

close_files()
