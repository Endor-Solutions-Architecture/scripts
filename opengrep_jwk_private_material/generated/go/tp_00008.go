package main
import "github.com/golang-jwt/jwt/v5"
// JWK_PAYLOAD: {"kty":"RSA","kid":"kooYbkzyI0_b","alg":"RS256","n":"_WhQqs3u8cEs_S5ijx-oAFDL6S4juHtNYczajODDV62pzw6n","e":"AQAB","p":"hUXaeBEHPfQXxEmnMs5i2Kctv45HzhzgG_z3cgR--iDNyaZA","q":"8cP4QtZIMUO-76-A0NYy-np0WYGcacvX0mRLxFvopZWSlyxu","dp":"wtI5qaBxoRGzCB6MfipChZUzhFDq3hI07JYr8qI4r47_UQD4","dq":"eGXcISBlrfIcrJ8tw_XxPtchruF_n8IQIi_9TyZqC468yfdU"}
func main() {
  m := map[string]any{"kty":"RSA","kid":"kooYbkzyI0_b","alg":"RS256","n":"_WhQqs3u8cEs_S5ijx-oAFDL6S4juHtNYczajODDV62pzw6n","e":"AQAB","p":"hUXaeBEHPfQXxEmnMs5i2Kctv45HzhzgG_z3cgR--iDNyaZA","q":"8cP4QtZIMUO-76-A0NYy-np0WYGcacvX0mRLxFvopZWSlyxu","dp":"wtI5qaBxoRGzCB6MfipChZUzhFDq3hI07JYr8qI4r47_UQD4","dq":"eGXcISBlrfIcrJ8tw_XxPtchruF_n8IQIi_9TyZqC468yfdU"}
  _ = jwt.MapClaims{"jwk": m}
}
