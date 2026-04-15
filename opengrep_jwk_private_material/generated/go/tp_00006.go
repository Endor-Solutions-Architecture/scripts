package main
import "github.com/golang-jwt/jwt/v5"
// JWK_PAYLOAD: {"kty":"EC","kid":"l0I9oqT2wi9y","alg":"ES256","crv":"P-256","x":"pMjCyAV24B0IxmgeRF_SmSJJ96zP4YyOykyEbz-prxo","y":"VRsgmp9IcAG9KpBKOvp_uw7k2rkhGtD3QBdQH3jNoyh","d":"RmCE9DosGtd4_cQTifFj6tbxekjLYX3eU3PRQHG3_eghTXtnymypFxGO6MxzlJW0"}
func main() {
  m := map[string]any{"kty":"EC","kid":"l0I9oqT2wi9y","alg":"ES256","crv":"P-256","x":"pMjCyAV24B0IxmgeRF_SmSJJ96zP4YyOykyEbz-prxo","y":"VRsgmp9IcAG9KpBKOvp_uw7k2rkhGtD3QBdQH3jNoyh","d":"RmCE9DosGtd4_cQTifFj6tbxekjLYX3eU3PRQHG3_eghTXtnymypFxGO6MxzlJW0"}
  _ = jwt.MapClaims{"jwk": m}
}
