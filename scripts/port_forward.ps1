
# List of services and ports
$Namespace = "default"
$services = @(
    @{ Name = "userservice"; LocalPort = 8080; RemotePort = 8080 },
    @{ Name = "balancereader"; LocalPort = 8081; RemotePort = 8080 },
    @{ Name = "orchestrator"; LocalPort = 8082; RemotePort = 8082 },
    @{ Name = "contact-sage"; LocalPort = 8083; RemotePort = 8083 },
    @{ Name = "money-sage"; LocalPort = 8084; RemotePort = 8084 },
    @{ Name = "anomaly-sage"; LocalPort = 8085; RemotePort = 8085 },
    @{ Name = "transaction-sage"; LocalPort = 8086; RemotePort = 8086 },
    @{ Name = "transactionhistory"; LocalPort = 8087; RemotePort = 8080 },
    @{ Name = "ledgerwriter"; LocalPort = 8088; RemotePort = 8080 },
    @{ Name = "contacts"; LocalPort = 8089; RemotePort = 8080 }
)

foreach ($svc in $services) {
    $cmd = "kubectl port-forward svc/$($svc.Name) $($svc.LocalPort):$($svc.RemotePort) -n $Namespace"
    $windowTitle = "Port Forward: $($svc.Name)"
    $commandString = "$Host.UI.RawUI.WindowTitle = '$windowTitle'; $cmd"
    Start-Process powershell -ArgumentList @('-NoExit', '-Command', $commandString)
}

