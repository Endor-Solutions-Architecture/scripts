package main
import "github.com/golang-jwt/jwt/v5"
// JWK_PAYLOAD: {"kty":"EC","kid":"vv018wPU1Jn5","alg":"ES256","crv":"P-256","x":"_4H8ZAwWuUpFVpvO6K_vcTUUjYq-70pgFUC4MMBRQOe","y":"BBbewJZ1N8z9dtOfff4pq9K3MknZu5x15flpaR4WlvQ","d":"HNelCi8Gpf93bsWv5EAUrJZGNb9PO8DrWg1oFO6WM9tphvoba5KTndsnL_d7Ohim"}
func main() {
  m := map[string]any{"kty":"EC","kid":"vv018wPU1Jn5","alg":"ES256","crv":"P-256","x":"_4H8ZAwWuUpFVpvO6K_vcTUUjYq-70pgFUC4MMBRQOe","y":"BBbewJZ1N8z9dtOfff4pq9K3MknZu5x15flpaR4WlvQ","d":"HNelCi8Gpf93bsWv5EAUrJZGNb9PO8DrWg1oFO6WM9tphvoba5KTndsnL_d7Ohim"}
  _ = jwt.MapClaims{"jwk": m}
}
