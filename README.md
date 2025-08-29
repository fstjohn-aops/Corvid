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

For playing sounds in your scripts:

```sh
# Success sound (ascending chord like create script)
success-sound() {
  play -q -n synth 0.1 sin 880
  play -q -n synth 0.1 sin 990
  play -q -n synth 0.1 sin 1100
}

# Failure sound (error alert pattern)
failure-sound() {
  play -q -n synth 0.2 sin 400
  play -q -n synth 0.1 sin 400
  play -q -n synth 0.2 sin 400
}

# Warning sound (two-tone alert)
warning-sound() {
  play -q -n synth 0.1 sin 800
  play -q -n synth 0.1 sin 800
}

# Quick notification sound
notify-sound() {
  play -q -n synth 0.1 sin 1500
}
```