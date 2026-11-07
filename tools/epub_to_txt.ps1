<#
.SYNOPSIS
    Converts an EPUB file to plain text using Calibre.
.PARAMETER InputFile
    Path to the source EPUB.
.PARAMETER OutputFile
    Path for the output TXT file.
.PARAMETER Force
    Allow replacing an existing output file.
.EXAMPLE
    .\epub_to_txt.ps1 -InputFile .\book.epub -OutputFile .\book.txt
#>

[CmdletBinding()]
param (
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateNotNullOrEmpty()]
    [string]$InputFile,

    [Parameter(Mandatory = $true, Position = 1)]
    [ValidateNotNullOrEmpty()]
    [string]$OutputFile,

    [switch]$Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$inputItem = Get-Item -LiteralPath $InputFile -ErrorAction Stop
if ($inputItem.PSIsContainer) {
    throw "Input path is a directory: $InputFile"
}
if ($inputItem.Extension -ine '.epub') {
    throw "Input file must have an .epub extension: $($inputItem.FullName)"
}
$inputPath = $inputItem.FullName

$outputPath = [System.IO.Path]::GetFullPath($OutputFile)
if ([System.IO.Path]::GetExtension($outputPath) -ine '.txt') {
    throw "Output file must have a .txt extension: $outputPath"
}

$outputDirectory = [System.IO.Path]::GetDirectoryName($outputPath)
if (-not (Test-Path -LiteralPath $outputDirectory -PathType Container)) {
    throw "Output directory does not exist: $outputDirectory"
}
if (Test-Path -LiteralPath $outputPath -PathType Container) {
    throw "Output path is a directory: $outputPath"
}
if ((Test-Path -LiteralPath $outputPath -PathType Leaf) -and -not $Force) {
    throw "Output file already exists. Use -Force to replace it: $outputPath"
}

$converterCommand = Get-Command -Name 'ebook-convert.exe' -CommandType Application -ErrorAction SilentlyContinue
if ($converterCommand) {
    $converterPath = $converterCommand.Source
} else {
    $candidatePaths = @()
    if ($env:ProgramFiles) {
        $candidatePaths += Join-Path -Path $env:ProgramFiles -ChildPath 'Calibre2\ebook-convert.exe'
    }
    if (${env:ProgramFiles(x86)}) {
        $candidatePaths += Join-Path -Path ${env:ProgramFiles(x86)} -ChildPath 'Calibre2\ebook-convert.exe'
    }

    $converterPath = $candidatePaths |
        Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } |
        Select-Object -First 1
}

if (-not $converterPath) {
    throw "Calibre's ebook-convert.exe was not found. Add it to PATH or install Calibre under Program Files."
}

& $converterPath $inputPath $outputPath
$conversionExitCode = $LASTEXITCODE
if ($conversionExitCode -ne 0) {
    throw "ebook-convert.exe failed with exit code $conversionExitCode."
}

if (-not (Test-Path -LiteralPath $outputPath -PathType Leaf)) {
    throw "Conversion completed without creating the output file: $outputPath"
}

$outputItem = Get-Item -LiteralPath $outputPath
if ($outputItem.Length -eq 0) {
    throw "Conversion created an empty output file: $outputPath"
}

Write-Output $outputItem.FullName
