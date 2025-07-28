# Tools and Stuff

## Random Commands I Wanted To Save

```sh
terraform state show "module.base_module.aws_instance.bastion[0]" | grep "id.*=" | awk '{print $3}'
```

## .zshrc

```sh
corvid-fly() {
  export PATH="$HOME/Source/Corvid/miscellaneous:$PATH"
}

corvid-fly() {
  export PATH=$(echo $PATH | sed -E "s|^$HOME/Source/Corvid/miscellaneous:||")
}
```