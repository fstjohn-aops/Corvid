# Gists and Stuff

## Random Commands I Wanted To Save

```
terraform state show "module.base_module.aws_instance.bastion[0]" | grep "id.*=" | awk '{print $3}'
```