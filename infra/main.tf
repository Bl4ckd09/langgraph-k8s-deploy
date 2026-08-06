resource "kind_cluster" "agentsvc" {
  name           = var.cluster_name
  wait_for_ready = true

  kind_config {
    kind        = "Cluster"
    api_version = "kind.x-k8s.io/v1alpha4"

    node {
      role = "control-plane"

      extra_port_mappings {
        container_port = var.node_port
        host_port      = var.node_port
        listen_address = "127.0.0.1"
      }
    }
  }
}

provider "kubernetes" {
  host                   = kind_cluster.agentsvc.endpoint
  cluster_ca_certificate = kind_cluster.agentsvc.cluster_ca_certificate
  client_certificate     = kind_cluster.agentsvc.client_certificate
  client_key             = kind_cluster.agentsvc.client_key
}

resource "terraform_data" "load_image" {
  triggers_replace = [var.image]

  provisioner "local-exec" {
    command     = "./scripts/load-image.sh"
    working_dir = var.repo_root

    environment = {
      CLUSTER = var.cluster_name
      IMAGE   = var.image
    }
  }

  depends_on = [kind_cluster.agentsvc]
}

resource "kubernetes_namespace_v1" "agentsvc" {
  metadata {
    name = var.namespace
  }
}

resource "kubernetes_config_map_v1" "agentsvc" {
  metadata {
    name      = "agentsvc-config"
    namespace = kubernetes_namespace_v1.agentsvc.metadata[0].name
  }

  data = {
    APP_VERSION = var.app_version
    LOG_LEVEL   = var.log_level
  }
}

resource "kubernetes_deployment_v1" "agentsvc" {
  metadata {
    name      = "agentsvc"
    namespace = kubernetes_namespace_v1.agentsvc.metadata[0].name
  }

  spec {
    replicas = var.replicas

    selector {
      match_labels = {
        app = "agentsvc"
      }
    }

    template {
      metadata {
        labels = {
          app = "agentsvc"
        }
      }

      spec {
        container {
          name              = "agentsvc"
          image             = var.image
          image_pull_policy = "IfNotPresent"

          port {
            container_port = 8000
          }

          env_from {
            config_map_ref {
              name = kubernetes_config_map_v1.agentsvc.metadata[0].name
            }
          }

          resources {
            requests = {
              cpu    = "50m"
              memory = "128Mi"
            }
            limits = {
              cpu    = "500m"
              memory = "512Mi"
            }
          }

          liveness_probe {
            http_get {
              path = "/healthz"
              port = 8000
            }
          }

          readiness_probe {
            http_get {
              path = "/readyz"
              port = 8000
            }
          }
        }
      }
    }
  }

  wait_for_rollout = true

  depends_on = [terraform_data.load_image]
}

resource "kubernetes_service_v1" "agentsvc" {
  metadata {
    name      = "agentsvc"
    namespace = kubernetes_namespace_v1.agentsvc.metadata[0].name
  }

  spec {
    selector = {
      app = "agentsvc"
    }

    port {
      port        = 80
      target_port = 8000
      node_port   = var.node_port
    }

    type = "NodePort"
  }
}
