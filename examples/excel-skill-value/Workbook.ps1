param(
    [Parameter(Mandatory)][ValidateSet('create', 'inspect', 'format', 'mutate')][string]$Action,
    [Parameter(Mandatory)][string]$Path
)
$ErrorActionPreference = 'Stop'
$excel = $null
$books = $null
$book = $null
$sheets = $null
$sheet = $null
$cells = $null
$refs = [Collections.Generic.List[object]]::new()
function Cell([string]$address) {
    $range = $sheet.Range($address)
    $refs.Add($range)
    return ,$range
}
function NumberFormat([object]$range, [string]$format) {
    $flags = if ($PSBoundParameters.ContainsKey('format')) {
        [Reflection.BindingFlags]::SetProperty
    } else {
        [Reflection.BindingFlags]::GetProperty
    }
    $arguments = if ($flags -eq [Reflection.BindingFlags]::SetProperty) { @($format) } else { $null }
    return $range.GetType().InvokeMember(
        'NumberFormat', $flags, $null, $range, $arguments,
        [Globalization.CultureInfo]::GetCultureInfo('en-US'))
}
try {
    $excel = New-Object -ComObject Excel.Application
    $excel.Visible = $false
    $excel.DisplayAlerts = $false
    $excel.AutomationSecurity = 3
    $books = $excel.Workbooks
    if ($Action -eq 'create') {
        if (Test-Path -LiteralPath $Path) { throw 'Refusing an existing fixture path.' }
        $book = $books.Add()
    } else {
        $book = $books.Open($Path, 0, ($Action -eq 'inspect'))
    }
    $sheets = $book.Worksheets
    $sheet = $sheets.Item(1)
    if ($Action -eq 'create') {
        $sheet.Name = 'Report'
        (Cell 'A1').Value2 = 'Account'
        (Cell 'B1').Value2 = 'Amount (USD)'
        (Cell 'C1').Value2 = 'Fractional rate'
        NumberFormat (Cell 'A2:A4') '@'
        (Cell 'A2').Value2 = '001'
        (Cell 'A3').Value2 = '002'
        (Cell 'A4').Value2 = '003'
        (Cell 'B2').Value2 = 135.25
        (Cell 'B3').Value2 = -210.5
        (Cell 'B4').Value2 = 0
        (Cell 'C2').Value2 = 0.45
        (Cell 'C3').Value2 = 0.12
        (Cell 'C4').Value2 = 0
        (Cell 'B5').Formula = '=SUM(B2:B4)'
        (Cell 'C5').Formula = '=AVERAGE(C2:C4)'
        (Cell 'A7').Value2 = 'Keep this existing note'
        $book.SaveAs([IO.Path]::GetFullPath($Path), 51)
    } elseif ($Action -eq 'format') {
        NumberFormat (Cell 'B2:B5') '$#,##0.00;($#,##0.00);"-"'
        NumberFormat (Cell 'C2:C5') '0.00%'
        $header = (Cell 'A1:C1').Font
        $refs.Add($header)
        $header.Bold = $true
        (Cell 'A:C').ColumnWidth = 22
        $book.Save()
    } elseif ($Action -eq 'mutate') {
        (Cell 'C2').Value2 = 45
        $book.Save()
    } else {
        $result = [Collections.Generic.List[object]]::new()
        foreach ($row in 1..7) {
            foreach ($column in @('A', 'B', 'C')) {
                $address = "$column$row"
                $range = Cell $address
                $font = $range.Font
                $refs.Add($font)
                $result.Add(@{
                    address = $address; value = $range.Value2; formula = $range.Formula
                    format = NumberFormat $range; bold = $font.Bold; text = $range.Text
                })
            }
        }
        $tables = $sheet.ListObjects
        $shapes = $sheet.Shapes
        $names = $book.Names
        $refs.Add($tables); $refs.Add($shapes); $refs.Add($names)
        @{
            cells = $result.ToArray(); sheet = $sheet.Name
            sheetCount = $sheets.Count; tables = $tables.Count
            shapes = $shapes.Count; names = $names.Count; calculation = $excel.Calculation
        } | ConvertTo-Json -Depth 8 -Compress
    }
} finally {
    if ($null -ne $book) { $book.Close($false) }
    if ($null -ne $excel) { $excel.Quit() }
    for ($i = $refs.Count - 1; $i -ge 0; $i--) {
        [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($refs[$i])
    }
    foreach ($reference in @($cells, $sheet, $sheets, $book, $books, $excel)) {
        if ($null -ne $reference) {
            [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($reference)
        }
    }
}
