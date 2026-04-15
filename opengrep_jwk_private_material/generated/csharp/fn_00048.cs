using Microsoft.IdentityModel.Tokens;
public class Fixture {
  public void Run() {
    // JWK_PAYLOAD: {"kty":"RSA","kid":"m8u3PoVhKU5Y","alg":"RS256","n":"uS55aiVRyyARAQpLTYv0vk7eNMC-U4Kf26LHw5pSMqQauquz","e":"AQAB"}
    var jwk = "{\"kty\":\"RSA\",\"kid\":\"m8u3PoVhKU5Y\",\"alg\":\"RS256\",\"n\":\"uS55aiVRyyARAQpLTYv0vk7eNMC-U4Kf26LHw5pSMqQauquz\",\"e\":\"AQAB\"}";
    var key = new JsonWebKey(jwk);
  }
}
