output "service_url" {
  value = "http://localhost:${var.node_port}"
}

output "cluster_name" {
  value = kind_cluster.agentsvc.name
}

output "namespace" {
  value = kubernetes_namespace_v1.agentsvc.metadata[0].name
}

output "kubeconfig_path" {
  value = kind_cluster.agentsvc.kubeconfig_path
}
