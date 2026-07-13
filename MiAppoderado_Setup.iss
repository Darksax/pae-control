; ============================================================================
;  MiAppoderado_Setup.iss — Inno Setup Script
;  MiAppoderado v1.5.4
;  Liceo Bicentenario Héroes de la Concepción, Laja, Chile
;
;  Requiere: Inno Setup 6.x  (https://jrsoftware.org/isinfo.php)
;  Ejecutar DESPUÉS de compilar el .exe con BUILD_WIN.bat
; ============================================================================

#define AppName      "MiAppoderado"
#define AppVersion   "1.5.4"
#define AppPublisher "Marcelo Muñoz — Liceo Bicentenario Héroes de la Concepción"
#define AppURL       "https://github.com/marcelomunoz/miappoderado"
#define AppExeName   "MiAppoderado.exe"
#define AppIcon      "assets\AppIcon.ico"
#define LicenseFile  "assets\license_es.txt"

[Setup]
; --- Identificadores únicos ---
AppId={{A3F8C2D1-4B7E-4A9F-8C3E-2D1F5A8B9C0E}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}
AppPublisher={#AppPublisher}
AppCopyright=Copyright (C) 2026 Marcelo Octavio Félix Muñoz Lizama

; --- Directorio de instalación ---
DefaultDirName={autopf}\MiAppoderado
DefaultGroupName={#AppName}
AllowNoIcons=no

; --- Salida ---
OutputDir=dist_installer
OutputBaseFilename=MiAppoderado_Setup_{#AppVersion}
SetupIconFile={#AppIcon}

; --- Compresión ---
Compression=lzma2/ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes

; --- Apariencia ---
WizardStyle=modern
WizardSizePercent=120
DisableWelcomePage=no
DisableDirPage=no
DisableProgramGroupPage=no

; --- Privilegios ---
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

; --- Plataforma ---
MinVersion=10.0.17763
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

; --- Idioma ---
ShowLanguageDialog=no

; --- Licencia ---
LicenseFile={#LicenseFile}

; --- Uninstall ---
UninstallDisplayIcon={app}\{#AppExeName}
UninstallDisplayName={#AppName} {#AppVersion}
CreateUninstallRegKey=yes

[Languages]
; Vendoreado en assets/Spanish.isl en vez de compiler:Languages\Spanish.isl —
; esa ruta depende de assets que no siempre vienen incluidos en la instalación
; de Inno Setup del runner de CI (choco y hasta el instalador oficial en modo
; silencioso fallaron en encontrarlos), así que se referencia un archivo del
; propio repo que siempre existe.
Name: "spanish"; MessagesFile: "assets\Spanish.isl"

[CustomMessages]
spanish.WelcomeLabel1=Bienvenido al asistente de instalación de [name]
spanish.WelcomeLabel2=Este asistente lo guiará a través de la instalación de [name/ver] en su equipo.%n%nSe recomienda cerrar todas las demás aplicaciones antes de continuar.%n%nHaga clic en Siguiente para continuar.
spanish.FinishedHeadingLabel=Instalación de [name] completada
spanish.FinishedLabel=La instalación de [name] ha finalizado exitosamente.%n%nPuede iniciar la aplicación haciendo clic en el acceso directo creado en el escritorio o en el menú de Inicio.

[Tasks]
Name: "desktopicon"; Description: "Crear acceso directo en el &Escritorio"; GroupDescription: "Accesos directos adicionales:"
Name: "quicklaunchicon"; Description: "Agregar al menú de &Inicio"; GroupDescription: "Accesos directos adicionales:"

[Files]
; Ejecutable principal (compilado por PyInstaller)
Source: "dist\{#AppExeName}"; DestDir: "{app}"; Flags: ignoreversion

; Icono (para desinstalador y accesos directos)
Source: "{#AppIcon}"; DestDir: "{app}\assets"; Flags: ignoreversion

; Licencia (copia informativa en la carpeta de instalación)
Source: "{#LicenseFile}"; DestDir: "{app}"; DestName: "LICENCIA.txt"; Flags: ignoreversion

; Archivo de configuración inicial (si existe)
; Source: "config_default.json"; DestDir: "{app}"; Flags: ignoreversion onlyifdoesntexist

[Icons]
; Acceso directo en menú Inicio
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\assets\AppIcon.ico"
Name: "{group}\Desinstalar {#AppName}"; Filename: "{uninstallexe}"

; Acceso directo en escritorio (si el usuario lo marcó)
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\assets\AppIcon.ico"; Tasks: desktopicon

[Run]
; Opción de ejecutar al finalizar
Filename: "{app}\{#AppExeName}"; Description: "Iniciar {#AppName} ahora"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Eliminar la base de datos local si el usuario desinstala (opcional — comentar si se quiere conservar)
; Type: files; Name: "{userappdata}\MiAppoderado\pae.db"
Type: dirifempty; Name: "{app}"

[Code]
// -----------------------------------------------------------------------
//  Página personalizada: mensaje de bienvenida institucional
// -----------------------------------------------------------------------
var
  WelcomePage: TWizardPage;
  WelcomeLabel: TLabel;

procedure InitializeWizard;
begin
  // Página de bienvenida institucional adicional
  WelcomePage := CreateCustomPage(
    wpWelcome,
    'MiAppoderado — Sistema de Gestión PAE',
    'Información del sistema'
  );

  WelcomeLabel := TLabel.Create(WelcomePage);
  with WelcomeLabel do
  begin
    Parent := WelcomePage.Surface;
    Left := 0;
    Top := 0;
    Width := WelcomePage.SurfaceWidth;
    Height := WelcomePage.SurfaceHeight;
    AutoSize := False;
    WordWrap := True;
    Caption :=
      'MiAppoderado es un sistema de gestión del Programa de Alimentación ' +
      'Escolar (PAE) desarrollado para el Liceo Bicentenario Héroes de la ' +
      'Concepción, Laja, Chile.' + #13#10 + #13#10 +
      'Este software permite:' + #13#10 +
      '  • Registro de asistencia al comedor escolar mediante escaneo de cédula' + #13#10 +
      '  • Gestión de períodos y semestres' + #13#10 +
      '  • Control de atrasos e inasistencias (módulo Inspectoría)' + #13#10 +
      '  • Sincronización en la nube con Supabase' + #13#10 +
      '  • Generación de reportes y estadísticas' + #13#10 + #13#10 +
      'Versión: 1.5.4' + #13#10 +
      'Desarrollado por: Marcelo Octavio Félix Muñoz Lizama' + #13#10 +
      'Institución: Liceo Bicentenario Héroes de la Concepción, RBD 14421' + #13#10 + #13#10 +
      'Requerimientos mínimos: Windows 10 (64-bit) versión 1809 o superior.' + #13#10 +
      'No requiere instalación de Python ni dependencias adicionales.';
  end;
end;

// -----------------------------------------------------------------------
//  Verificación de Windows 10 mínimo
// -----------------------------------------------------------------------
function InitializeSetup(): Boolean;
var
  Version: TWindowsVersion;
begin
  GetWindowsVersionEx(Version);
  if (Version.Major < 10) then
  begin
    MsgBox(
      'MiAppoderado requiere Windows 10 o superior.' + #13#10 +
      'Su sistema operativo no es compatible.',
      mbError, MB_OK
    );
    Result := False;
  end
  else
    Result := True;
end;
