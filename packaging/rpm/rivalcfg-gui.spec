Name:           rivalcfg-gui
Version:        4.17.0
Release:        4%{?dist}
Summary:        Unofficial GG-style GUI for SteelSeries mice (rivalcfg)
License:        WTFPL
URL:            https://github.com/Wookiee-/rivalcfg
Source0:        %{name}-%{version}.tar.gz

BuildArch:      noarch
BuildRequires:  python3-devel
Requires:       python3-hidapi
Requires:       python3-pyside6
Requires:       hicolor-icon-theme
Requires:       systemd

%description
Cross-desktop PySide6 GUI for rivalcfg: DPI stages, polling rate,
multi-zone RGB, button remapping with mouse diagram, JSON profiles,
system-tray mode with re-apply on login (survives reboot).

%prep
%autosetup -n %{name}-%{version}

%build
# nothing to compile (pure Python + rendered icons)

%install
PYLIB=$(python3 -c "import sysconfig; print(sysconfig.get_path('purelib'))")
install -d %{buildroot}${PYLIB}/rivalcfg
cp -r rivalcfg/* %{buildroot}${PYLIB}/rivalcfg/
python3 -m compileall -q %{buildroot}${PYLIB}/rivalcfg || :

install -d %{buildroot}%{_datadir}/rivalcfg-gui
cp -r gui/rivalcfg_gui %{buildroot}%{_datadir}/rivalcfg-gui/
cp gui/run_gui.py %{buildroot}%{_datadir}/rivalcfg-gui/
python3 -m compileall -q %{buildroot}%{_datadir}/rivalcfg-gui || :

install -D -m0755 packaging/rivalcfg-gui %{buildroot}%{_bindir}/rivalcfg-gui

install -D -m0644 packaging/rivalcfg-gui.desktop \
  %{buildroot}%{_datadir}/applications/rivalcfg-gui.desktop
install -D -m0644 packaging/rivalcfg-gui-autostart.desktop \
  %{buildroot}%{_sysconfdir}/xdg/autostart/rivalcfg-gui.desktop
install -D -m0644 packaging/rivalcfg-gui-apply.service \
  %{buildroot}%{_userunitdir}/rivalcfg-gui-apply.service
# point the unit at the packaged launcher (packaging/ ships a checkout path)
sed -i 's|^ExecStart=.*|ExecStart=%{_bindir}/rivalcfg-gui --apply-last|' \
  %{buildroot}%{_userunitdir}/rivalcfg-gui-apply.service

for s in 16 22 24 32 48 64 128 256; do
  install -D -m0644 packaging/icons/hicolor/${s}x${s}/apps/rivalcfg-gui.png \
    %{buildroot}%{_datadir}/icons/hicolor/${s}x${s}/apps/rivalcfg-gui.png
done
install -D -m0644 packaging/icons/rivalcfg-gui.svg \
  %{buildroot}%{_datadir}/icons/hicolor/scalable/apps/rivalcfg-gui.svg

%post
# allow regular users to open the mice (needs root — we are root here)
python3 -m rivalcfg --update-udev >/dev/null 2>&1 || :
update-desktop-database /usr/share/applications >/dev/null 2>&1 || :
gtk-update-icon-cache -f -t /usr/share/icons/hicolor >/dev/null 2>&1 || :
%systemd_user_post rivalcfg-gui-apply.service

%preun
%systemd_user_preun rivalcfg-gui-apply.service

%postun
update-desktop-database /usr/share/applications >/dev/null 2>&1 || :
gtk-update-icon-cache -f -t /usr/share/icons/hicolor >/dev/null 2>&1 || :
%systemd_user_postun_with_restart rivalcfg-gui-apply.service

%files
%{python3_sitelib}/rivalcfg/
%{_datadir}/rivalcfg-gui/
%{_bindir}/rivalcfg-gui
%{_datadir}/applications/rivalcfg-gui.desktop
%{_sysconfdir}/xdg/autostart/rivalcfg-gui.desktop
%{_userunitdir}/rivalcfg-gui-apply.service
%{_datadir}/icons/hicolor/*/apps/rivalcfg-gui.png
%{_datadir}/icons/hicolor/scalable/apps/rivalcfg-gui.svg

%changelog
* Thu Sep 24 2026 rivalcfg-gui 4.17.0-4
- Bundle mouse diagram SVGs (installed pkg had none); debounce tray toggle so double-click opens
* Thu Sep 24 2026 rivalcfg-gui 4.17.0-3
- Tray autostart re-applies saved settings on login
* Thu Sep 24 2026 rivalcfg-gui 4.17.0-2
- GUI cleanup: drop unsupported-feature placeholders; desktop/icon cache scriptlets
* Thu Sep 24 2026 rivalcfg-gui 4.17.0-1
- GG-style GUI: tray, reboot persistence, hicolor icons
