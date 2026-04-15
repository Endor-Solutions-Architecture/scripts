package main
import "github.com/golang-jwt/jwt/v5"
// JWK_PAYLOAD: {"kty":"RSA","kid":"DmFtxb46Us2t","alg":"RS256","n":"hjidOHEMklyH9O6v0BOPJEvXKfa5aDx_4s3iGr3J9PbDHGjR","e":"AQAB"}
func main() {
  m := map[string]any{"kty":"RSA","kid":"DmFtxb46Us2t","alg":"RS256","n":"hjidOHEMklyH9O6v0BOPJEvXKfa5aDx_4s3iGr3J9PbDHGjR","e":"AQAB"}
  _ = jwt.MapClaims{"jwk": m}
}
