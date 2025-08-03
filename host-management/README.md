# Bastion Hosts

## Are They in Teleport?

### Yes

- Academy Dev
- Academy Prod
- Torchboard Prod
- Strapi Dev
- Academy Staging

### No

- AoPS-Dev.AWSAdministratorAccess (i-07b3358ecea1740d5) (44.236.8.119)
- AoPS-Prod.AWSAdministratorAccess (i-0249e455f3cb62e89) (13.52.217.23)
- BAClassroom-Prod.AWSAdministratorAccess (i-0adc39336c16034a7) (54.191.69.176)
- BAClassroom-Staging.AWSAdministratorAccess (i-0fb3f6e11c106d1af) (54.186.104.8)
- BACurriculum-Prod.AWSAdministratorAccess (i-07e8a4e16b3cca2a7) (52.36.70.116)
- BACurriculum-Staging.AWSAdministratorAccess (i-051845a60059c7452) (54.69.110.41)
- CS-Prod.AWSAdministratorAccess (i-0070060b6f19277aa) (34.215.92.46)
- CS-Staging.AWSAdministratorAccess (i-03ce73c849391964a) (54.184.187.205)
- Encounter-Prod.AWSAdministratorAccess (i-07555827c8c7d06bc) (44.229.131.220)
- Eng-Trove.AWSAdministratorAccess (i-081555104461c2754) (54.218.85.149)
- Grader-Prod.AWSAdministratorAccess (i-05b81832fd942acf2) (44.231.7.12)
- Grader-Staging.AWSAdministratorAccess: neither of bastion hosts (i-07e737978f05252bf) (54.70.251.169) (i-0fe66163f83cbceb0) (54.214.254.128)
- ML-Dev.AWSAdministratorAccess (i-01b6bdf2e11c07ccc) (44.245.147.238)
- ML-Staging.AWSAdministratorAccess (i-02c5452f50ad6c8a4) (52.37.4.171)
- PartnerApi-Prod.AWSAdministratorAccess (i-0860784c340f5ec35) (44.246.0.118)
- PartnerApi-Staging.AWSAdministratorAccess (i-06387523a9c692938) (44.245.125.136)
- Platform-Prod.AWSAdministratorAccess: N. Virginia, no (i-0a72130b54a7df72f) 
- Services-Dev.AWSAdministratorAccess (i-02d3405cc55b37811) (52.53.236.50)
- Services-Prod.AWSAdministratorAccess (i-0f6d2596d979e2323) (18.144.66.226)
- Services-Staging.AWSAdministratorAccess (i-00df761c500688993) (54.176.81.199)
- Strapi-Prod.AWSAdministratorAccess (i-0567442bea2e34eca) (35.81.93.226)
- Strapi-Staging.AWSAdministratorAccess (i-0dba66f7584f73cbf) (44.234.248.215)
- Thrid-Prod.AWSAdministratorAccess (i-0b3a999721896d815) (35.162.148.49)
- Thrid-Staging.AWSAdministratorAccess (i-03398a7248bcda344) (52.32.144.123)
- VCVC-Dev.AWSAdministratorAccess (i-0870c46e327ce18ce) (44.239.167.228)

Any accounts not listed did not have a bastion host in any region as far as I 
could tell.

## For machines with python3 older than 3.5 or something

pip3 install --user "pip<21.0"

sudo apt install -y build-essential libssl-dev libffi-dev python3-dev

pip3 install --user "PyYAML<6.0"
pip3 install --user "cryptography<42.0"

pip3 install --user ansible boto3 botocore

## For Services hosts

```
sudo amazon-linux-extras enable ansible2
sudo yum clean metadata
sudo yum -y install ansible
```
