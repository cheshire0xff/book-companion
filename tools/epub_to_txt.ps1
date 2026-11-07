<#
.SYNOPSIS
    Converts an EPUB file to plain text and an HTML package using Calibre.
.PARAMETER InputFile
    Path to the source EPUB.
.PARAMETER OutputFile
    Path for the output TXT file. A sibling <name>-html directory is also created.
.PARAMETER Force
    Allow replacing an existing TXT file and HTML output directory.
.EXAMPLE
    .\epub_to_txt.ps1 -InputFile .\book.epub -OutputFile .\book.txt
    Creates .\book.txt and .\book-html\.
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
$outputBaseName = [System.IO.Path]::GetFileNameWithoutExtension($outputPath)
if ([string]::IsNullOrWhiteSpace($outputBaseName)) {
    throw "Output file must have a base name: $outputPath"
}
if (Test-Path -LiteralPath $outputPath -PathType Container) {
    throw "Output path is a directory: $outputPath"
}
if ((Test-Path -LiteralPath $outputPath -PathType Leaf) -and -not $Force) {
    throw "Output file already exists. Use -Force to replace it: $outputPath"
}

$htmlOutputDirectory = Join-Path -Path $outputDirectory -ChildPath ($outputBaseName + '-html')
if (Test-Path -LiteralPath $htmlOutputDirectory) {
    if (-not (Test-Path -LiteralPath $htmlOutputDirectory -PathType Container)) {
        throw "HTML output path exists as a file: $htmlOutputDirectory"
    }
    if (-not $Force) {
        throw "HTML output directory already exists. Use -Force to replace it: $htmlOutputDirectory"
    }
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

function Invoke-EbookConvert {
    param (
        [Parameter(Mandatory = $true)]
        [string]$Destination
    )

    & $converterPath $inputPath $Destination
    $conversionExitCode = $LASTEXITCODE
    if ($conversionExitCode -ne 0) {
        throw "ebook-convert.exe failed with exit code $conversionExitCode for output: $Destination"
    }
}

Invoke-EbookConvert -Destination $outputPath
if (-not (Test-Path -LiteralPath $outputPath -PathType Leaf)) {
    throw "Conversion completed without creating the output file: $outputPath"
}

$outputItem = Get-Item -LiteralPath $outputPath
if ($outputItem.Length -eq 0) {
    throw "Conversion created an empty output file: $outputPath"
}

$temporaryHtmlOutputDirectory = Join-Path -Path $outputDirectory -ChildPath (
    $outputBaseName + '-html-' + [guid]::NewGuid().ToString('N')
)
try {
    Invoke-EbookConvert -Destination $temporaryHtmlOutputDirectory
    if (-not (Test-Path -LiteralPath $temporaryHtmlOutputDirectory -PathType Container)) {
        throw "HTML conversion completed without creating an output directory: $temporaryHtmlOutputDirectory"
    }

    $htmlFiles = @(
        Get-ChildItem -LiteralPath $temporaryHtmlOutputDirectory -Recurse -File |
            Where-Object { $_.Extension -in @('.html', '.htm', '.xhtml') -and $_.Length -gt 0 }
    )
    if ($htmlFiles.Count -eq 0) {
        throw "HTML conversion created no non-empty HTML files: $temporaryHtmlOutputDirectory"
    }

    if (Test-Path -LiteralPath $htmlOutputDirectory) {
        Remove-Item -LiteralPath $htmlOutputDirectory -Recurse -Force
    }
    Move-Item -LiteralPath $temporaryHtmlOutputDirectory -Destination $htmlOutputDirectory
} finally {
    if (Test-Path -LiteralPath $temporaryHtmlOutputDirectory) {
        Remove-Item -LiteralPath $temporaryHtmlOutputDirectory -Recurse -Force
    }
}

if (-not (Test-Path -LiteralPath $htmlOutputDirectory -PathType Container)) {
    throw "HTML conversion completed without creating the output directory: $htmlOutputDirectory"
}

Write-Output $outputItem.FullName
Write-Output $htmlOutputDirectory
