# Tools and Stuff

## Random Commands I Wanted To Save

```sh
terraform state show "module.base_module.aws_instance.bastion[0]" | grep "id.*=" | awk '{print $3}'
```

## .zshrc

```sh
add-tools-to-path() {
  export PATH="$HOME/Source/Corvid/miscellaneous:$PATH"
}

remove-tools-from-path() {
  export PATH=$(echo $PATH | sed -E "s|^$HOME/Source/Corvid/miscellaneous:||")
}
```