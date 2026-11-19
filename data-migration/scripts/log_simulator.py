import os
import argparse


parser = argparse.ArgumentParser(description="Log file creation and modifier simulator")

parser.add_argument("log_name", type=str, help="File name of the log file")
parser.add_argument("--multiplexed", type=bool, help="Specifies a multiplexed log file")
parser.add_argument("--push_sample_rows", type=bool, help="Adds example rows to the log file")



if __name__ == "__main__":
    args = parser.parse_args()
    
    if not os.path.exists("test/" + args.log_name):
        content = r"""
Z:\Experiments\RR\MacsScenarios\RR_sample_test traffic_V17 06  11 2026 vg.txt
run 
date 12062026
scenario Z:\Experiments\RR\MacsScenarios\RR_sample_test traffic_V17 06  11 2026 vg.txt
experiment condition 
macs version MACS-AOL-2019
file name: Z:/Experiments/DATA/RR/AOL-DeeJay_Macs_FlightState_zoa_252_1_2026-06-12_11-53-27.log
"""
        if args.multiplexed:
            content += "discriminator 1\tcol1\tcol2\tcol3\n"
            content += "discriminator 2\tcol1\tcol2\tcol3\n"
        else:
            content += "col 1\tcol 2\tcol 3\n"

        content += "END HEADER\n"

        with open("test/" + args.log_name, "w") as file:
            file.write(content)

    if args.push_sample_rows:
        content = ""

        if args.multiplexed:
            content += "discriminator 1\tvalue 1\tvalue 2\tvalue 3\n"
            content += "discriminator 2\tvalue 1\tvalue 2\tvalue 3\n"
        else:
            content += "value 1\t value 2\tvalue 3\n"

        with open("test/" + args.log_name, "a") as file:
            file.write(content)
