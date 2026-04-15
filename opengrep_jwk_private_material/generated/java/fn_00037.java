import com.nimbusds.jose.jwk.JWK;
class Fixture {
  void run() throws Exception {
    // JWK_PAYLOAD: {"kty":"RSA","kid":"xMC3G02QKAc1","alg":"RS256","n":"RhghkL_snJayekBEf-hJAxWwKhBj-aepf3gPpoLlh3lupcr6","e":"AQAB"}
    String jwk = "{\"kty\":\"RSA\",\"kid\":\"xMC3G02QKAc1\",\"alg\":\"RS256\",\"n\":\"RhghkL_snJayekBEf-hJAxWwKhBj-aepf3gPpoLlh3lupcr6\",\"e\":\"AQAB\"}";
    JWK.parse(jwk);
  }
}
