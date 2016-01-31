#!/usr/bin/python
#
# Copyright (c) 2014 Evgeny Gridasov (evgeny.gridasov@gmail.com)
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
#
import urllib2
import argparse
import re
try:
	import simplejson as json
except ImportError:
	import json

REDSHIFT_REGIONS = [
	"us-east-1",
	"us-west-2",
	"us-gov-west-1",
	"eu-west-1",
	"eu-central-1",
	"ap-southeast-1",
	"ap-southeast-2",
	"ap-northeast-1",
	"ap-northeast-2",
	"sa-east-1"
]

REDSHIFT_INSTANCE_TYPES = [
	"dw1.xlarge",
	"dw1.8xlarge",
	"dw2.xlarge",
	"dw2.8xlarge",
]
JSON_NAME_TO_REGIONS_API = {
	"us-east" : "us-east-1",
	"us-east-1" : "us-east-1",
	"us-west" : "us-west-1",
	"us-west-1" : "us-west-1",
	"us-west-2" : "us-west-2",
	"us-gov-west-1" : "us-gov-west-1",
	"eu-ireland" : "eu-west-1",
	"eu-west-1" : "eu-west-1",
	"eu-frankfurt" : "eu-central-1",
	"eu-central-1" : "eu-central-1",
	"apac-sin" : "ap-southeast-1",
	"ap-southeast-1" : "ap-southeast-1",
	"ap-southeast-2" : "ap-southeast-2",
	"apac-syd" : "ap-southeast-2",
	"apac-tokyo" : "ap-northeast-1",
	"ap-northeast-1" : "ap-northeast-1",
	"ap-northeast-2" : "ap-northeast-2",
	"sa-east-1" : "sa-east-1"
}

REDSHIFT_ONDEMAND_URL = "http://a0.awsstatic.com/pricing/1/redshift/pricing-on-demand-redshift-instances.min.js"
REDSHIFT_ONDEMAND_PREVIOUS_URL = "http://a0.awsstatic.com/pricing/1/redshift/previous-generation/pricing-on-demand-redshift-instances.min.js"
REDSHIFT_RESERVED_V2_URL = "http://a0.awsstatic.com/pricing/1/redshift/pricing-reserved-redshift-instances.min.js"
REDSHIFT_RESERVED_PREVIOIUS_V2_URL = "http://a0.awsstatic.com/pricing/1/redshift/previous-generation/pricing-reserved-redshift-instances.min.js"
REDSHIFT_1Y_HEAVY_RESERVATION_URL = "http://a0.awsstatic.com/pricing/1/redshift/pricing-one-year-heavy-reserved-instances.min.js"
REDSHIFT_3Y_HEAVY_RESERVATION_URL = "http://a0.awsstatic.com/pricing/1/redshift/pricing-three-years-heavy-reserved-instances.min.js"

DEFAULT_CURRENCY = "USD"


def _load_data(url):
	f = urllib2.urlopen(url).read()
	f = re.sub("/\\*[^\x00]+\\*/", "", f, 0, re.M)
	f = re.sub("([a-zA-Z0-9]+):", "\"\\1\":", f)
	f = re.sub(";", "\n", f)
	def callback(json):
		return json
	data = eval(f, {"__builtins__" : None}, {"callback" : callback} )
	return data


def get_redshift_reserved_instances_prices(filter_region=None, filter_instance_type=None):
	""" Get RedShift reserved instances prices. Results can be filtered by region """

	get_specific_region = (filter_region is not None)
	get_specific_instance_type = (filter_instance_type is not None)

	currency = DEFAULT_CURRENCY

	urls = [
		REDSHIFT_1Y_HEAVY_RESERVATION_URL,
		REDSHIFT_3Y_HEAVY_RESERVATION_URL,
		
		REDSHIFT_RESERVED_V2_URL,
		REDSHIFT_RESERVED_PREVIOIUS_V2_URL
	]

	result_regions = []
	result_regions_index = {}
	result = {
		"config" : {
			"currency" : currency,
		},
		"regions" : result_regions
	}

	for u in urls:
		data = _load_data(u)
		if "config" in data and data["config"] and "regions" in data["config"] and data["config"]["regions"]:
			for r in data["config"]["regions"]:
				if "region" in r and r["region"]:
					region_name = JSON_NAME_TO_REGIONS_API[r["region"]]
					if get_specific_region and filter_region != region_name:
						continue
					if region_name in result_regions_index:
						instance_types = result_regions_index[region_name]["instanceTypes"]
					else:
						instance_types = []
						result_regions.append({
							"region" : region_name,
							"instanceTypes" : instance_types
						})
						result_regions_index[region_name] = result_regions[-1]
						
					if "instanceTypes" in r:
						for it in r["instanceTypes"]:
							# old style reserved instances
							if "tiers" in it:
								for s in it["tiers"]:
									_type = s["size"]
	
									if get_specific_instance_type and _type != filter_instance_type:
										continue
									
									prices = {
										"hourly" : None,
										"upfront" : None,
										"term" : None,
									}
	
									instance_types.append({
										"type" : _type,
										"reservation" : "heavy",
										"prices" : prices
									})
	
									for price_data in s["valueColumns"]:
										price = None
										try:
											price = float(re.sub("[^0-9\.]", "", price_data["prices"][currency]))
										except ValueError:
											price = None
	
										if price_data["name"] == "yrTerm1":
											prices["upfront"] = price
											prices["term"] = "1year"
										elif price_data["name"] == "yrTerm1Hourly":
											prices["hourly"] = price
										elif price_data["name"] == "yrTerm3":
											prices["upfront"] = price
											prices["term"] = "3year"
										elif price_data["name"] == "yrTerm3Hourly":
											prices["hourly"] = price
							
							# new ri types
							if "type" in it and "terms" in it:
								_type = it["type"]
								if get_specific_instance_type and _type != filter_instance_type:
										continue
								for term in it["terms"]:
									for purchaseOpt in term["purchaseOptions"]:
										upfront = ""
										hourly = ""
										prices = {}
										for price_data in purchaseOpt["valueColumns"]:
											if price_data["name"] == "upfront":
												upfront = (price_data["prices"]["USD"]).replace(",", "")
											if price_data["name"] == "monthlyStar":
												hourly = "%.3f" % (float(str.replace(price_data["prices"]["USD"],",","")) * 12 / 365 / 24)
										prices["upfront"] = upfront
										prices["hourly"] = hourly
										if term["term"] == "yrTerm1":
											prices["term"] = "1year"
										if term["term"] == "yrTerm3":
											prices["term"] = "3year"
										instance_types.append({
													"type" : _type,
													"reservation" : purchaseOpt["purchaseOption"],
													"prices" : prices
												})

	return result



def get_redshift_ondemand_instances_prices(filter_region=None, filter_instance_type=None, filter_multiaz=None, filter_db=None):
	""" Get RedShift on-demand instances prices. Results can be filtered by region """

	get_specific_region = (filter_region is not None)
	get_specific_instance_type = (filter_instance_type is not None)

	currency = DEFAULT_CURRENCY

	result_regions = []
	result = {
		"config" : {
			"currency" : currency,
			"unit" : "perhr"
		},
		"regions" : result_regions
	}
	
	urls = [
		REDSHIFT_ONDEMAND_URL,
		REDSHIFT_ONDEMAND_PREVIOUS_URL,
	]

	for u in urls:
		data = _load_data(u)
		if "config" in data and data["config"] and "regions" in data["config"] and data["config"]["regions"]:
			for r in data["config"]["regions"]:
				if "region" in r and r["region"]:
					region_name = JSON_NAME_TO_REGIONS_API[r["region"]]
					if get_specific_region and filter_region != region_name:
						continue	
					
					instance_types = []
					if "instanceTypes" in r:
						for it in r["instanceTypes"]:
							if "tiers" in it:
								for s in it["tiers"]:
									_type = s["size"]
	
									if get_specific_instance_type and _type != filter_instance_type:
										continue
									
									price = None
									try:
										price = float(re.sub("[^0-9\.]", "", s["valueColumns"][0]["prices"][currency]))
									except ValueError:
										price = None
									
									instance_types.append({
										"type" : _type,
										"price" : price
									})
	
						result_regions.append({
							"region" : region_name,
							"instanceTypes" : instance_types
						})
	return result

if __name__ == "__main__":
	def none_as_string(v):
		if v == 0:
			return "0"
		if not v:
			return ""
		else:
			return v

	try:
		import argparse 
	except ImportError:
		print "ERROR: You are running Python < 2.7. Please use pip to install argparse:   pip install argparse"


	parser = argparse.ArgumentParser(add_help=True, description="Print out the current prices of RedShift instances")
	parser.add_argument("--type", "-t", help="Show ondemand or reserved instances", choices=["ondemand", "reserved"], required=True)
	parser.add_argument("--filter-region", "-fr", help="Filter results to a specific region", choices=REDSHIFT_REGIONS, default=None)
	parser.add_argument("--filter-type", "-ft", help="Filter results to a specific instance type", choices=REDSHIFT_INSTANCE_TYPES, default=None)
	parser.add_argument("--format", "-f", choices=["json", "table", "csv"], help="Output format", default="table")

	args = parser.parse_args()

	if args.format == "table":
		try:
			from prettytable import PrettyTable
		except ImportError:
			print "ERROR: Please install 'prettytable' using pip:    pip install prettytable"

	data = None
	if args.type == "ondemand":
		data = get_redshift_ondemand_instances_prices(args.filter_region, args.filter_type)
	elif args.type == "reserved":
		data = get_redshift_reserved_instances_prices(args.filter_region, args.filter_type)

	if data == None:
		print "filter produced no results"
		exit()
		
	if args.format == "json":
		print json.dumps(data)
	elif args.format == "table":
		x = PrettyTable()

		if args.type == "ondemand":
			try:			
				x.set_field_names(["region", "type", "price"])
			except AttributeError:
				x.field_names = ["region", "type", "price"]

			try:
				x.aligns[-1] = "l"
			except AttributeError:
				x.align["price"] = "l"

			for r in data["regions"]:
				region_name = r["region"]
				for it in r["instanceTypes"]:
					x.add_row([region_name, it["type"], none_as_string(it["price"])])
		elif args.type == "reserved":
			try:
				x.set_field_names(["region", "type", "reservation", "term", "price", "upfront"])
			except AttributeError:
				x.field_names = ["region", "type", "reservation", "term", "price", "upfront"]

			try:
				x.aligns[-1] = "l"
				x.aligns[-2] = "l"
			except AttributeError:
				x.align["price"] = "l"
				x.align["upfront"] = "l"
			
			for r in data["regions"]:
				region_name = r["region"]
				for it in r["instanceTypes"]:
					x.add_row([region_name, it["type"], it["reservation"], it["prices"]["term"], none_as_string(it["prices"]["hourly"]), none_as_string(it["prices"]["upfront"])])
		
		print x
	elif args.format == "csv":
		if args.type == "ondemand":
			print "region,type,price"
			for r in data["regions"]:
				region_name = r["region"]
				for it in r["instanceTypes"]:
					print "%s,%s,%s" % (region_name, it["type"], none_as_string(it["price"]))
		elif args.type == "reserved":
					print "region,type,reservation,term,price,upfront"
					for r in data["regions"]:
						region_name = r["region"]
						for it in r["instanceTypes"]:
							for term in it["prices"]:
								print "%s,%s,%s,%s,%s,%s" % (region_name, it["type"], it["reservation"], it["prices"]["term"], none_as_string(it["prices"]["hourly"]), none_as_string(it["prices"]["upfront"]))
