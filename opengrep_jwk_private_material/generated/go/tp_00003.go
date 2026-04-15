package main
import "github.com/golang-jwt/jwt/v5"
// JWK_PAYLOAD: {"kty":"RSA","kid":"By4Rp8oPcWtZ","alg":"RS256","n":"1wC2MxqCAV3_GMNt2wxLPxHwROXJPbwIZhUTYT7gbvQ3VWtA","e":"AQAB","p":"d517jTrNVu6K2t4hOtD7Z6aF6bvJHZo8amaXKpUXAYR0mhk9","q":"qBIvUgQu_nhTaT_ra4k-OarLJyTPy-5TTiTrg2t2USVR6Gv2","dp":"mhYoniaUc5QEeK9Yp4pmDJaaroWHi-iF4GOmsYEoLLDecJMq","dq":"AqQ7Oep8_nx-Eykc5PB6owSxoKgqQhP3rJIOCVG7IjFbzN_G"}
func main() {
  m := map[string]any{"kty":"RSA","kid":"By4Rp8oPcWtZ","alg":"RS256","n":"1wC2MxqCAV3_GMNt2wxLPxHwROXJPbwIZhUTYT7gbvQ3VWtA","e":"AQAB","p":"d517jTrNVu6K2t4hOtD7Z6aF6bvJHZo8amaXKpUXAYR0mhk9","q":"qBIvUgQu_nhTaT_ra4k-OarLJyTPy-5TTiTrg2t2USVR6Gv2","dp":"mhYoniaUc5QEeK9Yp4pmDJaaroWHi-iF4GOmsYEoLLDecJMq","dq":"AqQ7Oep8_nx-Eykc5PB6owSxoKgqQhP3rJIOCVG7IjFbzN_G"}
  _ = jwt.MapClaims{"jwk": m}
}
