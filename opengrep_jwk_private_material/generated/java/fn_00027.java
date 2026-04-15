import com.nimbusds.jose.jwk.JWK;
class Fixture {
  void run() throws Exception {
    // JWK_PAYLOAD: {"kty":"RSA","kid":"TG-Y1whaGJXf","alg":"RS256","n":"DqZdAFrvVdBQmJuv474c08psAJxR3bSMZN9bCKLOryXAutPG","e":"AQAB"}
    String jwk = "{\"kty\":\"RSA\",\"kid\":\"TG-Y1whaGJXf\",\"alg\":\"RS256\",\"n\":\"DqZdAFrvVdBQmJuv474c08psAJxR3bSMZN9bCKLOryXAutPG\",\"e\":\"AQAB\"}";
    JWK.parse(jwk);
  }
}
