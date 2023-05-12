# Termux-Mpv

This is a wrapper for mpv on [Termux](http://termux.com). It displays a notification bar with media controls. ***Modified to use the media-title property if no metadata is found in order to display youtube video titles**

![Screenshot](/Screenshots/Notification-Media-Controls-small.png)

## Requirements

* [Termux:API](https://play.google.com/store/apps/details?id=com.termux.api) App from Google Play (or FDroid)

### Packages: 

* `termux-api`
* `python`
* `mpv`
```
pkg install termux-api python mpv
```

## Installation

```
pip install git+https://github.com/kpg-anon/Termux-Mpv-Yt-dlp
```
*the above snippet requires git to be installed `pkg install git`*

## Usage

`termuxmpv` is a drop-in replacement for `mpv`. All arguments get forwarded to mpv. For convenience, you can add the following alias to your `~/.bashrc` or `~/.zshrc` file:

```
alias mpva="termuxmpv $*"
```
