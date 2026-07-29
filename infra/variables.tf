variable "cluster_name" {
  type    = string
  default = "langgraph-demo"
}

variable "namespace" {
  type    = string
  default = "agentsvc"
}

variable "image" {
  type    = string
  default = "docker.io/library/langgraph-agentsvc:dev"
}

variable "replicas" {
  type    = number
  default = 2
}

variable "node_port" {
  type    = number
  default = 30080
}

variable "app_version" {
  type    = string
  default = "0.1.0"
}

variable "log_level" {
  type    = string
  default = "INFO"
}

variable "repo_root" {
  type    = string
  default = ".."
}
